import io
import mss
import psutil
from PIL import Image
import win32gui


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


def capture_screen_bytes(quality=50, scale=(640, 360)) -> bytes:
    """Mengambil screenshot langsung ke RAM buffer (format WebP)."""
    with mss.MSS() as sct:
        monitor = sct.monitors[1]  # Monitor Utama
        sct_img = sct.grab(monitor)

        # Konversi ke PIL Image & Resize
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail(scale)

        # Buffer di RAM (io.BytesIO)
        ram_buffer = io.BytesIO()
        img.save(ram_buffer, format="WEBP", quality=quality)
        return ram_buffer.getvalue()