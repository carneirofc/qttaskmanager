"""Pure psutil collection — no Qt imports so this module is safe to run
in a subprocess (ProcessPoolExecutor worker). Main process GIL is never
touched while this runs."""
import psutil
from collections import defaultdict

ProcessRow = dict   # keys: pid name status cpu mem_mb threads user ports exe cmdline
ConnRow = tuple     # (pid, name, laddr, raddr, state, family)


def collect_all() -> tuple[list[ProcessRow], list[ConnRow]]:
    pid_ports: dict[int, list[str]] = defaultdict(list)
    conns: list[ConnRow] = []

    try:
        pid_name: dict[int, str] = {
            p.pid: p.info["name"] or ""
            for p in psutil.process_iter(["name"])
        }
    except Exception:
        pid_name = {}

    try:
        for c in psutil.net_connections(kind="inet"):
            pid = c.pid or 0
            laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
            raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
            state = c.status or ""
            family = "IPv6" if c.family.name == "AF_INET6" else "IPv4"
            conns.append((pid, pid_name.get(pid, ""), laddr, raddr, state, family))
            if pid and c.laddr:
                pid_ports[pid].append(
                    f"{c.laddr.port}" + (f" ({state})" if state else "")
                )
    except psutil.AccessDenied:
        pass

    procs: list[ProcessRow] = []
    for p in psutil.process_iter(
        ["pid", "name", "status", "cpu_percent", "memory_info",
         "username", "num_threads", "exe", "cmdline"]
    ):
        try:
            info = p.info
            mem = info["memory_info"]
            pid = info["pid"]
            ports = pid_ports.get(pid, [])
            raw_cmd = info.get("cmdline") or []
            procs.append({
                "pid":     pid,
                "name":    info["name"] or "",
                "status":  info["status"] or "",
                "cpu":     info["cpu_percent"] or 0.0,
                "mem_mb":  round(mem.rss / 1024 / 1024, 1) if mem else 0.0,
                "threads": info["num_threads"] or 0,
                "user":    info["username"] or "",
                "ports":   ", ".join(sorted(set(ports))),
                "exe":     info.get("exe") or "",
                "cmdline": " ".join(raw_cmd) if raw_cmd else "",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda r: r["pid"])
    conns.sort(key=lambda r: (r[2], r[0]))
    return procs, conns
