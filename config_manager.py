import json
import os
import sys

# Path permanen di C:\ProgramData\WatchersAgent\config.json
PROGRAM_DATA_DIR = os.path.join(
    os.environ.get("ProgramData", "C:\\ProgramData"), "WatchersAgent"
)
CONFIG_FILE_PATH = os.path.join(PROGRAM_DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "SERVER_URL": "https://agent.tebaslahandev.my.id",
    "RECONNECT_INTERVAL": 3,
    "VERSION": "0.0.0"
}


def ensure_dir_exists():
    r"""Memastikan direktori C:\ProgramData\WatchersAgent tersedia."""
    if not os.path.exists(PROGRAM_DATA_DIR):
        os.makedirs(PROGRAM_DATA_DIR, exist_ok=True)


def save_config(new_config: dict):
    """Menyimpan konfigurasi baru ke file config.json."""
    ensure_dir_exists()  # Cukup pastikan foldernya ada, JANGAN memanggil ensure_config_exists()
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=4)
        print(f"[✓] Berhasil menyimpan config ke: {CONFIG_FILE_PATH}")
    except Exception as e:
        print(f"[!] Gagal menyimpan config.json: {e}")


def ensure_config_exists():
    """Memastikan file config.json ada. Jika belum ada, buat dengan nilai default."""
    ensure_dir_exists()
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"[*] File config tidak ditemukan. Membuat config default...")
        save_config(DEFAULT_CONFIG)


def load_config() -> dict:
    """Membaca konfigurasi dari file config.json di %ProgramData%."""
    ensure_config_exists()
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Gagal membaca config.json, menggunakan default: {e}")
        return DEFAULT_CONFIG


def restart_process():
    """Menghentikan proses saat ini agar NSSM / Watchdog menyalakannya kembali."""
    print("[*] Merestart WatchersAgent...")
    os._exit(0)