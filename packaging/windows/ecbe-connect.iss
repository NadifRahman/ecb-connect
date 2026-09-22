#define AppName "ECBE Connect - Unofficial"
#define AppVersion "0.1.1"

[Setup]
AppId={{C31CE617-ECBE-4D43-9721-AB22CBE05C01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ECBE Connect contributors
DefaultDirName={localappdata}\Programs\ECBE Connect
DefaultGroupName=ECBE Connect
PrivilegesRequired=lowest
OutputDir=..\..\release
OutputBaseFilename=ecbe-connect-{#AppVersion}-windows-x86_64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\ECBE Connect.exe
LicenseFile=..\..\LICENSE
InfoBeforeFile=disclaimer.txt
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\ECBE Connect\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\ecbe-connect-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ECBE Connect"; Filename: "{app}\ECBE Connect.exe"
Name: "{userdesktop}\ECBE Connect"; Filename: "{app}\ECBE Connect.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\ECBE Connect.exe"; Description: "Open ECBE Connect"; Flags: nowait postinstall skipifsilent
