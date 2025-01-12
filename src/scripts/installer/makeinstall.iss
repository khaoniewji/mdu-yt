; Inno Setup Script
[Setup]
AppName=Youtube Downloader
AppVersion=2024.09.24
DefaultDirName={localappdata}\kaoniewji\mduyoutube
DefaultGroupName=Youtube Downloader
OutputDir=..\..\installer
OutputBaseFilename=mduinstall-20240924b4
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes

[Files]
Source: "..\..\dist\mdu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Youtube Downloader"; Filename: "{app}\mdu.exe"
Name: "{userdesktop}\Youtube Downloader"; Filename: "{app}\mdu.exe"

[Run]
Filename: "{app}\mdu.exe"; Description: "Launch Youtube Downloader"; Flags: nowait postinstall skipifsilent
