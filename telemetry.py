import io
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


def capture_screen_bytes(quality=50, scale=(640, 360)) -> bytes:
    global _sct_instance

    try:
        if _sct_instance is None:
            _sct_instance = mss.mss()

        # Gunakan monitor utama [1] atau fall-back ke [0] jika monitors[1] bermasalah
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

    except (ScreenShotError, Exception) as e:
        # Jika GDI melempar error, reset instance mss agar dibuat ulang di iterasi berikutnya
        _sct_instance = None
        # Kembalikan buffer kosong agar loop telemetri tetap berjalan tanpa membanting exception crash
        return b""