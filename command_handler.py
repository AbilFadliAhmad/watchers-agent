import os
import subprocess
import sys
import webbrowser
import time
import socket

# Helper Function Run Macro Worker
def send_key_event_to_service(key_str: str, action: str) -> bool:
    """Mengirim event tombol ke WatchersService via socket lokal."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(1.0)
        client.connect(("127.0.0.1", 58888))

        # Format pesan: INJECT_KEY:<key_str>:<action>
        payload = f"INJECT_KEY:{key_str}:{action}"
        client.sendall(payload.encode("utf-8"))
        client.close()
        return True
    except Exception as e:
        print(f"[MACRO SOCKET ERROR] Gagal mengirim event tombol: {e}")
        return False

def run_macro_worker(events: list):
    """Worker makro yang meneruskan eksekusi ketikan ke WatchersService."""
    print(
        f"[MACRO] Memulai eksekusi {len(events)} event ketikan via Service..."
    )

    for event in events:
        delay = event.get("delay", 0)
        key_str = event.get("key", "")
        action = event.get("action", "press")

        # 1. Jeda waktu
        if delay > 0:
            time.sleep(delay)

        if not key_str:
            continue

        # 2. Kirim event ke WatchersService (SYSTEM)
        send_key_event_to_service(key_str, action)

    print("[MACRO] Eksekusi makro selesai.")

# Helper Function shutdown & restart
def send_ipc_command(command: str) -> bool:
    """Mengirim perintah instan (SHUTDOWN/RESTART) ke WatchersService via Local Socket."""
    try:
        # Hubungi WatchersService di localhost port 58888
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(("127.0.0.1", 58888))
        client.sendall(command.encode("utf-8"))
        client.close()
        print(f"[✓] Berhasil mengirim sinyal IPC: {command}")
        return True
    except Exception as e:
        print(f"[!] Gagal menghubungi WatchersService via IPC: {e}")
        return False

def execute_shutdown():
    """Memicu shutdown via WatchersService (SYSTEM)."""
    print("[*] Menerima perintah Shutdown, menghubungi WatchersService...")
    send_ipc_command("SHUTDOWN")
def execute_restart():
    """Memicu restart via WatchersService (SYSTEM)."""
    print("[*] Menerima perintah Restart, menghubungi WatchersService...")
    send_ipc_command("RESTART")

def execute_open_url(url: str):
    webbrowser.open(url, new=2)


def handle_file_chunk(
    filename: str, chunk_data: bytes, append: bool = True
) -> str:
    """Menyimpan pecahan file yang dikirim dari server secara streaming."""
    download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    file_path = os.path.join(download_dir, filename)

    mode = "ab" if append else "wb"
    with open(file_path, mode) as f:
        f.write(chunk_data)

    return file_path


def execute_ota_update(new_exe_bytes: bytes):
    """Memperbarui executable aplikasi menggunakan teknik Rename & Replace."""

    # 1. PROTEKSI UTAMA: Pastikan hanya berjalan pada file .exe hasil build PyInstaller
    if not getattr(sys, "frozen", False):
        print(
            "[!] OTA Update dibatalkan: Aplikasi berjalan dalam mode skrip Python (.py), bukan file terkompilasi (.exe).",
            flush=True,
        )
        return False

    current_exe = sys.executable
    old_exe = current_exe + ".old"
    temp_exe = current_exe + ".new"

    # 1. Tulis file baru ke file temporary
    with open(temp_exe, "wb") as f:
        f.write(new_exe_bytes)

    # 2. Hapus versi old jika ada
    if os.path.exists(old_exe):
        try:
            os.remove(old_exe)
        except Exception:
            pass

    # 3. Rename file running exe saat ini menjadi .old
    os.rename(current_exe, old_exe)

    # 4. Rename file baru menjadi nama file utama
    os.rename(temp_exe, current_exe)

    # 5. Jalankan executable baru dan hentikan proses saat ini
    subprocess.Popen([current_exe])
    sys.exit(0)