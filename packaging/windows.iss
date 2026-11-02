#ifndef AppVersion
  #error AppVersion is required
#endif
[Setup]
AppId={{AB1C41CF-B5D9-4A07-8467-F6E81FC20A21}
AppName=TJKSub
AppVersion={#AppVersion}
AppPublisher=konata91008
AppPublisherURL=https://github.com/konata91008/KonataWhisperGUI-Public
AppSupportURL=https://github.com/konata91008/KonataWhisperGUI-Public/issues
DefaultDirName={localappdata}\Programs\TJKSub
DefaultGroupName=TJKSub
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and not arm64
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.18362
OutputDir=..\release-artifacts
OutputBaseFilename=TJKSub-{#AppVersion}-windows-x64-setup
SetupIconFile=generated\TJKSub.ico
UninstallDisplayIcon={app}\TJKSub.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\dist\TJKSub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\TJKSub"; Filename: "{app}\TJKSub.exe"
Name: "{autodesktop}\TJKSub"; Filename: "{app}\TJKSub.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\TJKSub.exe"; Description: "Launch TJKSub"; Flags: nowait postinstall skipifsilent
