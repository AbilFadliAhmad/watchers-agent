import os
import subprocess
import sys
import webbrowser
from pynput import keyboard
import time

# Inisialisasi Controller Keyboard pynput
kb = keyboard.Controller()
# Pemetaan (Mapping) Nama Key dari JavaScript ke Objek pynput.keyboard.Key
SPECIAL_KEYS = {
    "Key.ctrl": keyboard.Key.ctrl_l,
    "Key.shift": keyboard.Key.shift_l,
    "Key.alt": keyboard.Key.alt_l,
    "Key.cmd": keyboard.Key.cmd,
    "Key.enter": keyboard.Key.enter,
    "Key.backspace": keyboard.Key.backspace,
    "Key.tab": keyboard.Key.tab,
    "Key.esc": keyboard.Key.esc,
    "Key.right": keyboard.Key.right,
    "Key.left": keyboard.Key.left,
    "Key.up": keyboard.Key.up,
    "Key.down": keyboard.Key.down,
    "Space": keyboard.Key.space,
    " ": keyboard.Key.space,
}


def run_macro_worker(events: list):
    """Worker fungsi yang berjalan di thread terpisah untuk mengeksekusi urutan tombol."""
    print(
        f"[MACRO] Memulai eksekusi {len(events)} event ketikan otomatis..."
    )

    for event in events:
        delay = event.get("delay", 0)
        key_str = event.get("key", "")
        action = event.get("action", "press")

        # 1. Terapkan jeda waktu (delay)
        if delay > 0:
            time.sleep(delay)

        if not key_str:
            continue

        # 2. Tentukan Objek Key (Tombol Spesial vs Karakter Biasa)
        if key_str in SPECIAL_KEYS:
            key_obj = SPECIAL_KEYS[key_str]
        elif key_str.startswith("Key."):
            # Fallback dinamis untuk tombol pynput lainnya
            attr_name = key_str.replace("Key.", "")
            key_obj = getattr(keyboard.Key, attr_name, key_str)
        else:
            # Karakter biasa (a-z, 0-9, simbol)
            key_obj = key_str

        # 3. Simulasi Penekanan / Pelepasan Tombol
        try:
            if action == "press":
                kb.press(key_obj)
            elif action == "release":
                kb.release(key_obj)
        except Exception as e:
            print(f"[MACRO ERROR] Gagal menekan '{key_str}': {e}")

    print("[MACRO] Eksekusi ketikan otomatis selesai.")

def execute_shutdown():
    os.system("shutdown /s /t 0 ")

def execute_restart():
    # Perintah /r untuk restart
    os.system("shutdown /r /t 0")


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