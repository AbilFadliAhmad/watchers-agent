import io
import socket
import mss
from mss.exception import ScreenShotError
import psutil
from PIL import Image
import win32gui
import ctypes


def get_open_windows() -> list[str]:
    """Mengambil daftar semua judul jendela aplikasi yang sedang terbuka dan terlihat."""
    open_windows = []

    def enum_windows_callback(hwnd, extra):
        # Menyaring hanya jendela yang terlihat dan memiliki judul (bukan proses tersembunyi)
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.strip():
                open_windows.append(title.strip())

    try:
        win32gui.EnumWindows(enum_windows_callback, None)
        return open_windows if open_windows else ["Desktop"]
    except Exception:
        return []

def get_system_telemetry() -> dict:
    """Mengambil data beban CPU, RAM, dan daftar aplikasi yang dibuka client."""
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "open_windows": get_open_windows(),
    }

# Set DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

_sct_instance = None


def request_frame_from_service() -> bytes:
    """Meminta bytes gambar Winlogon dari WatchersService (SYSTEM) via Local Socket."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(1.0)
        client.connect(("127.0.0.1", 58888))
        client.sendall(b"GET_WINLOGON_FRAME")

        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk

        client.close()
        return data
    except Exception:
        return b""

def capture_screen_bytes(quality=50, scale=(640, 360)) -> bytes:
    global _sct_instance

    # 1. Coba capture normal menggunakan mss (Sangat cepat di Desktop)
    try:
        if _sct_instance is None:
            _sct_instance = mss.mss()

        monitor = (
            _sct_instance.monitors[1]
            if len(_sct_instance.monitors) > 1
            else _sct_instance.monitors[0]
        )
        sct_img = _sct_instance.grab(monitor)

        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail(scale)

        ram_buffer = io.BytesIO()
        img.save(ram_buffer, format="WEBP", quality=quality)
        return ram_buffer.getvalue()

    except (ScreenShotError, Exception):
        # 2. Jika mss gagal (saat Winlogon / Lock Screen), reset instance mss
        _sct_instance = None

        # 3. Fallback: Ambil dari WatchersService (Winlogon / Lock Screen)
        try:
            raw_bytes = request_frame_from_service()
            if raw_bytes:
                img = Image.open(io.BytesIO(raw_bytes))
                img.thumbnail(scale)

                ram_buffer = io.BytesIO()
                img.save(ram_buffer, format="WEBP", quality=quality)
                return ram_buffer.getvalue()
        except Exception:
            pass

        # 4. PASTIKAN SELALU MENGEMBALIKAN b"" JIKA GAGAL (BUKAN None)
        return b""