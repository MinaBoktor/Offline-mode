[Setup]
AppName=Offline Mode
AppVersion=1.0
DefaultDirName={pf}\OfflineMode
DefaultGroupName=Offline Mode
UninstallDisplayIcon={app}\offline.ico
Compression=lzma
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=OfflineModeSetup
SetupIconFile=offline.ico

[Files]
Source: "dist\OfflineMode.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\OfflineMode_service.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "offline.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Offline Mode"; Filename: "{app}\OfflineMode.exe"
Name: "{group}\Uninstall Offline Mode"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\OfflineMode_service.exe"; Parameters: "--install"; StatusMsg: "Installing service..."; Flags: runhidden
Filename: "{app}\OfflineMode_service.exe"; Parameters: "--start"; StatusMsg: "Starting service..."; Flags: runhidden
Filename: "{app}\OfflineMode.exe"; Parameters: "--silent"; Description: "Run Offline Mode at startup"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\OfflineMode_service.exe"; Parameters: "--stop"; RunOnceId: "StopService"; Flags: runhidden
Filename: "{app}\OfflineMode_service.exe"; Parameters: "--remove"; RunOnceId: "RemoveService"; Flags: runhidden