; Inno Setup script for QtTaskManager.
;
; Wraps the single onefile executable produced by pyside6-deploy/Nuitka
; (dist\QtTaskManager.exe) into a per-user setup.exe with Start Menu /
; optional desktop shortcuts and an uninstaller.
;
; Build:  iscc /DAppVersion=0.1.0 installer.iss
; (build.ps1 -Installer passes the version read from pyproject.toml.)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "QtTaskManager"
#define AppPublisher "carneirofc"
#define AppURL "https://github.com/carneirofc/qttaskmanager"
#define AppExeName "QtTaskManager.exe"

[Setup]
; A unique, stable GUID identifies the app across upgrades/uninstalls.
AppId={{8F0C8C6E-2A1B-4D3C-9E5F-7A6B1C2D3E4F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}

; Per-user install: no admin/UAC prompt, lands in %LocalAppData%\Programs.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=app.ico

; Emit the installer into dist\ next to the exe it wraps.
OutputDir=dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
