import concurrent.futures
import ctypes
import io
from PIL import Image, ImageGrab
import mss
import psutil
import win32gui
from agent_logger import log_error, log_info, get_current_session_id

# ================================================================
# 1. SET DPI AWARENESS (PENTING UNTUK WINDOWS 11 SCALING 125%/150%)
# ================================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(
        2
    )  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Thread pool khusus untuk eksekusi aman dengan timeout (Mencegah Zombie)
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# Global Memory Cache: Menyimpan frame terakhir yang BERHASIL ditangkap (Anti-Layar Hitam)
last_valid_frame_bytes = None


# ================================================================
# 2. ENUMERATE WINDOWS (DENGAN TIMEOUT PROTEKSI)
# ================================================================
def _enum_windows_safe():
    open_windows = []

    def callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title.strip():
                    open_windows.append(title.strip())
        except Exception:
            pass

    try:
        win32gui.EnumWindows(callback, None)
        return open_windows if open_windows else ["Desktop"]
    except Exception:
        return ["Desktop"]


def get_open_windows() -> list[str]:
    """Mengambil daftar jendela aktif dengan batas waktu 1 detik agar tidak hang."""
    try:
        future = executor.submit(_enum_windows_safe)
        return future.result(timeout=1.0)
    except Exception:
        return ["Desktop"]


def get_system_telemetry() -> dict:
    """Mengambil data beban CPU, RAM, dan daftar aplikasi."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
    except Exception:
        cpu, ram = 0, 0

    return {
        "cpu": cpu,
        "ram": ram,
        "open_windows": get_open_windows(),
    }


# ================================================================
# 3. DUAL-ENGINE CAPTURE (MSS + PIL FALLBACK + CACHE CHECK)
# ================================================================
def _raw_capture_mss(quality, scale):
    """Metode 1: MSS (Utama - Sangat Cepat)"""
    with mss.mss() as sct:
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        sct_img = sct.grab(monitor)

        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img.thumbnail(scale)

        # Deteksi jika gambar yang ditangkap 100% hitam polos (Session Lock)
        extrema = img.getextrema()
        is_black = all(e == (0, 0) for e in extrema)
        if is_black:
            raise ValueError("Layar hitam terdeteksi (Session Lock)")

        ram_buffer = io.BytesIO()
        img.save(ram_buffer, format="WEBP", quality=quality)
        return ram_buffer.getvalue()


def _raw_capture_pil(quality, scale):
    """Metode 2: PIL ImageGrab (Cadangan jika MSS driver error)"""
    img = ImageGrab.grab(all_screens=False)
    img.thumbnail(scale)

    extrema = img.getextrema()
    is_black = all(e == (0, 0) for e in extrema)
    if is_black:
        raise ValueError("Layar hitam terdeteksi (PIL)")

    ram_buffer = io.BytesIO()
    img.save(ram_buffer, format="WEBP", quality=quality)
    return ram_buffer.getvalue()


def _internal_capture(quality, scale):
    # Coba Engine 1 (MSS)
    try:
        return _raw_capture_mss(quality, scale)
    except Exception:
        pass

    # Coba Engine 2 (PIL ImageGrab)
    try:
        return _raw_capture_pil(quality, scale)
    except Exception:
        pass

    raise RuntimeError("Seluruh engine capture gagal.")


# ================================================================
# 4. CAPTURE SCREEN DENGAN GARANSI TIMEOUT & CACHE RECOVERY
# ================================================================
def capture_screen_bytes(quality=50, scale=(640, 360)) -> bytes:
    """Mengambil screenshot langsung ke RAM buffer (format WebP).

    Garansi 100% Bebas Zombie Process & Tidak Mengirim Layar Hitam.
    """
    global last_valid_frame_bytes

    session_id = get_current_session_id()
    if session_id == 0:
        log_error(
            "CRITICAL: Agent berjalan di SESSION 0! Windows melarang akses layar monitor dari Session 0."
        )

    try:
        # Jalankan capture di thread terpisah dengan HARD TIMEOUT 1.5 Detik
        future = executor.submit(_internal_capture, quality, scale)
        frame_bytes = future.result(timeout=1.5)

        # Catat log sukses (Hanya sekali di awal atau saat recovery)
        if last_valid_frame_bytes is None:
            log_info(
                f"Screenshot PERTAMA BERHASIL ditangkap di Session {session_id} | Ukuran: {len(frame_bytes)} bytes"
            )

        # Simpan frame sukses ini ke RAM cache global
        last_valid_frame_bytes = frame_bytes
        return frame_bytes

    except Exception as e:
        log_error("Gagal mengambil screenshot layar", exc=e)
        # SOLUSI ANTI LAYAR HITAM & ANTI ZOMBIE:
        # Jika OS mengunci layar/gagal capture, kirimkan CACHE SCREENSHOT TERAKHIR yang sukses
        if last_valid_frame_bytes is not None:
            log_info(
                "Menggunakan cache screenshot terakhir karena layar saat ini terkunci/gagal."
            )
            return last_valid_frame_bytes

        # Fallback awal jika baru pertama kali dinyalakan dan belum ada cache sama sekali
        dummy = Image.new("RGB", scale, color=(30, 30, 35))
        ram_buffer = io.BytesIO()
        dummy.save(ram_buffer, format="WEBP", quality=30)
        return ram_buffer.getvalue()