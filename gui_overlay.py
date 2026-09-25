import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QVBoxLayout, QWidget
import ctypes
from ctypes import wintypes
# --- GLOBAL VARIABLES ---
hook_id = None  # Inisialisasi variabel global agar dapat diakses dari fungsi manapun

# --- WINDOWS API CONSTANTS & HOOK ---
user32 = ctypes.windll.user32

WH_KEYBOARD_LL = 13
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt Key


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


# 1. Definisikan prototype HOOKPROC
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# 2. Atur argtypes dan restype untuk SetWindowsHookExW & UnhookWindowsHookEx
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK

user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL


# 3. Buat Fungsi Callback Python
def low_level_keyboard_proc(nCode, wParam, lParam):
    if nCode >= 0:
        # Kembalikan nilai 1 untuk memblokir penekanan tombol (misal: Alt+Tab, Win Key)
        return 1
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# 4. WAJIB SIMPAN DI VARIABEL GLOBAL agar tidak kena Garbage Collector
c_keyboard_callback = HOOKPROC(low_level_keyboard_proc)


def start_keyboard_hook():
    global hook_id  # Beritahu Python untuk memperbarui variabel global hook_id

    # Pasang Windows Low-Level Hook
    hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, c_keyboard_callback, None, 0
    )

    if not hook_id:
        print("[HOOK ERROR] Gagal memasang Windows Low-Level Keyboard Hook!")
    else:
        print(f"[HOOK OK] Keyboard Hook berhasil dipasang (ID: {hook_id})")

    return hook_id


def stop_keyboard_hook():
    global hook_id
    if hook_id is not None:
        user32.UnhookWindowsHookEx(hook_id)
        print(f"[HOOK UNHOOKED] Keyboard Hook #{hook_id} berhasil dilepas.")
        hook_id = None


# --- PYQT6 LOCK SCREEN WIDGET ---
class LockScreenWidget(QWidget):

    def __init__(self, message="DIKUNCI OLEH GURU"):
        super().__init__()

        # Otomatis hancurkan objek C++ dari RAM saat jendela ditutup
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Hapus Qt.WindowType.Tool (Gunakan Window + Frameless + StaysOnTop)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Aktifkan Low-Level Hook Sistem Operasi untuk mematikan Input keyboard
        start_keyboard_hook()

        # Sembunyikan Kursor Mouse
        self.setCursor(Qt.CursorShape.BlankCursor)

        # Susun Layout & Elemen UI
        layout = QVBoxLayout()
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "color: white; font-size: 50px; font-weight: bold; font-family: 'Segoe UI';"
        )

        self.setStyleSheet("background-color: black;")
        layout.addWidget(label)
        self.setLayout(layout)

        # Tampilkan Fullscreen SETELAH Layout Siap
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Kembalikan fungsi keyboard saat di-unlock oleh guru
        stop_keyboard_hook()
        super().closeEvent(event)

# Simpan referensi global agar tidak terhapus oleh Garbage Collector
_active_popup = None


def show_popup_message(title: str, message: str = 'testing doang cuy'):
    """Menampilkan jendela pesan pop-up secara non-blocking agar tidak merusak event loop asyncio."""
    global _active_popup
    print('title : ', title)
    print('message : ', message)

    app = QApplication.instance() or QApplication(sys.argv)

    # Bersihkan popup lama jika masih terbuka
    if _active_popup is not None:
        try:
            _active_popup.close()
            _active_popup.deleteLater()
        except RuntimeError:
            pass

    _active_popup = QMessageBox()
    _active_popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    _active_popup.setWindowFlags(
        Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
    )
    _active_popup.setWindowTitle(title)
    _active_popup.setText(message)
    _active_popup.setIcon(QMessageBox.Icon.Information)

    # BARIS KUNCI: Gunakan .show() bukan .exec()
    _active_popup.show()
    _active_popup.raise_()
    _active_popup.activateWindow()