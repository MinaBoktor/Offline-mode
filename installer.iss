[Setup]
AppName=OfflineMode
AppVersion=1.0
AppPublisher=Myna LLC
AppPublisherURL=https://example.com
AppSupportURL=https://example.com
AppUpdatesURL=https://example.com
DefaultDirName={autopf}\OfflineMode
DefaultGroupName=OfflineMode
AllowNoIcons=yes
LicenseFile=
InfoBeforeFile=
InfoAfterFile=
OutputDir=dist\Output
OutputBaseFilename=OfflineMode_Setup
SetupIconFile=offline.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\OfflineMode.exe
UninstallDisplayName=OfflineMode - Offline Bookmark Manager

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "startuprun"; Description: "Start with Windows"; GroupDescription: "Startup Options:"; Flags: checkablealone

[Files]
Source: "dist\setup_package\OfflineMode.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\setup_package\OfflineMode_service.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\setup_package\offline.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\setup_package\service.bat"; DestDir: "{app}"; DestName: "manage_service.bat"; Flags: ignoreversion
Source: "dist\setup_package\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\OfflineMode"; Filename: "{app}\OfflineMode.exe"; IconFilename: "{app}\offline.ico"
Name: "{group}\Service Manager"; Filename: "{app}\manage_service.bat"; IconFilename: "{app}\offline.ico"
Name: "{group}\{cm:UninstallProgram,OfflineMode}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\OfflineMode"; Filename: "{app}\OfflineMode.exe"; IconFilename: "{app}\offline.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\OfflineMode"; Filename: "{app}\OfflineMode.exe"; IconFilename: "{app}\offline.ico"; Tasks: quicklaunchicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "OfflineMode"; ValueData: """{app}\OfflineMode.exe"" --silent"; Tasks: startuprun

[Run]
Filename: "{app}\OfflineMode_service.exe"; Parameters: "install"; StatusMsg: "Installing background sync service..."; Flags: runhidden waituntilterminated
Filename: "{app}\OfflineMode_service.exe"; Parameters: "start"; StatusMsg: "Starting background sync service..."; Flags: runhidden waituntilterminated
Filename: "{app}\OfflineMode.exe"; Description: "{cm:LaunchProgram,OfflineMode}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\OfflineMode_service.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated
Filename: "{app}\OfflineMode_service.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check if we're running as administrator
  if not IsAdminLoggedOn() then
  begin
    MsgBox('This installer requires administrator privileges to install the background service.' + #13#10 + 
           'Please run this installer as administrator.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Additional service installation verification
    Log('Verifying service installation...');
    
    // Check if service was installed successfully
    if Exec('sc', 'query OfflineModeService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode = 0 then
      begin
        Log('Service installed and running successfully');
        // Show success message
        MsgBox('OfflineMode has been installed successfully!' + #13#10 + #13#10 +
               '✓ Application installed' + #13#10 +
               '✓ Background sync service installed and started' + #13#10 +
               '✓ Automatic sync every 12 hours is now active' + #13#10 + #13#10 +
               'You can now use OfflineMode to sync your Raindrop.io bookmarks offline.',
               mbInformation, MB_OK);
      end else
      begin
        Log('Service installation may have failed, showing troubleshooting message');
        MsgBox('OfflineMode has been installed, but there may be an issue with the background service.' + #13#10 + #13#10 +
               'You can manually manage the service using:' + #13#10 +
               '• Start Menu → OfflineMode → Service Manager' + #13#10 +
               '• Or run manage_service.bat from the installation folder' + #13#10 + #13#10 +
               'The main application will still work for manual syncing.',
               mbInformation, MB_OK);
      end;
    end else
    begin
      Log('Could not verify service status');
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Clean up any remaining service traces
    Log('Cleaning up service remnants...');
    Exec('sc', 'delete OfflineModeService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  // Show information about the service on the ready page
  if CurPageID = wpReady then
  begin
    if MsgBox('OfflineMode will install a background service that automatically syncs your bookmarks every 12 hours.' + #13#10 + #13#10 +
              'This service will:' + #13#10 +
              '• Run in the background automatically' + #13#10 +
              '• Start with Windows' + #13#10 +
              '• Sync your Raindrop.io bookmarks every 12 hours' + #13#10 +
              '• Use minimal system resources' + #13#10 + #13#10 +
              'Do you want to continue with the installation?',
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;