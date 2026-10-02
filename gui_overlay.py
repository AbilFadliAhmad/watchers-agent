import os
import platform
import sys
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QIcon, QPainter, QPixmap
import ctypes
from ctypes import wintypes

# String SVG Ikon Power / Shutdown (Warna Putih)
SHUTDOWN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="35" height="35" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
    <line x1="12" y1="2" x2="12" y2="12"></line>
</svg>
"""

def render_svg_icon(svg_str: str, size: int = 24) -> QIcon:
    """Mengubah string XML SVG menjadi QIcon secara in-memory."""
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)

# --- GLOBAL VARIABLES ---
hook_id = None

# --- WINDOWS API CONSTANTS & HOOK ---
user32 = ctypes.windll.user32
WH_KEYBOARD_LL = 13


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# 1. Tentukan argtypes & restype secara eksplisit (mencegah OverflowError 64-bit)
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK

user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL

user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_longlong

# 2. DAFTAR TOMBOL YANG DIBLOKIR (BLACK_LIST)
# Menggunakan set {} untuk pencarian instan O(1)
BLOCKED_KEYS = {
    0x09,  # Tab (VK_TAB)
    0x1B,  # Esc (VK_ESCAPE)
    0x12,  # Alt (VK_MENU)
    0xA4,  # Left Alt (VK_LMENU)
    0xA5,  # Right Alt (VK_RMENU)
    0x5B,  # Left Windows Key (VK_LWIN)
    0x5C,  # Right Windows Key (VK_RWIN)
}


def low_level_keyboard_proc(nCode, wParam, lParam):
    if nCode < 0:
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    # Pembacaan memori langsung via pointer C (Tanpa ctypes.cast yang lambat)
    vk_code = KBDLLHOOKSTRUCT.from_address(lParam).vkCode

    # Blokir HANYA jika tombol adalah:
    # 1. F1 sampai F12 (VK_F1: 0x70 s/d VK_F12: 0x7B)
    # 2. Tab, Esc, Alt, atau Windows Key (di dalam BLOCKED_KEYS)
    if (0x70 <= vk_code <= 0x7B) or (vk_code in BLOCKED_KEYS):
        return 1  # Stop pemrosesan (BLOKIR)

    # Izinkan SELURUH tombol lainnya (Huruf, Angka, Symbol, Shift, Enter, Backspace, Space, dll)
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


# 3. Simpan callback agar tidak di-Garbage Collect oleh Python
c_keyboard_callback = HOOKPROC(low_level_keyboard_proc)


def start_keyboard_hook():
    global hook_id
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
import asyncio
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit

class LockScreenWidget(QWidget):

    def __init__(self, message="DIKUNCI OLEH GURU", sio_client=None, device_id=""):
        super().__init__()
        self.sio_client = sio_client
        self.device_id = device_id

        # Otomatis hancurkan objek C++ dari RAM saat jendela ditutup
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Konfigurasi Window (Frameless + Always on Top)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Aktifkan Low-Level Hook Keyboard OS
        start_keyboard_hook()

        # Tampilkan kursor panah biasa agar user dapat melihat posisi saat mengetik/klik
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Styling Background Utama (Slate Dark)
        self.setStyleSheet("background-color: #0f172a;")

        # --- LAYOUT UTAMA (MASTER) ---
        master_layout = QVBoxLayout()
        master_layout.setContentsMargins(24, 24, 24, 24)

        # Spacer Atas untuk mendorong konten ke tengah vertikal
        master_layout.addStretch()

        # --- LAYOUT TENGAH (KONTEN UTAMA: IKON, PESAN & INPUT) ---
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(16)

        # 1. Ikon Kunci Besar
        self.icon_label = QLabel("🔒")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 80px; color: #f59e0b;")

        # 2. Pesan Kunci Utama
        self.msg_label = QLabel(message)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet(
            "color: #f8fafc; font-size: 28px; font-weight: bold; font-family: 'Segoe UI';"
        )

        # 3. Petunjuk Input
        self.sub_label = QLabel("Masukkan kata sandi untuk membuka akses komputer:")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-family: 'Segoe UI';")

        # 4. Kolom Input Password
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Masukkan kata sandi...")
        self.password_input.setFixedWidth(320)
        self.password_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #ffffff;
                border: 2px solid #334155;
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 15px;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
            }
        """)

        # EVENT: Jalankan verifikasi saat tombol ENTER ditekan di kolom input
        self.password_input.returnPressed.connect(self.handle_unlock_request)

        # 5. Label Status Hasil Verifikasi (Error / Info)
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: bold;")

        # Susun Elemen Konten ke Layout Tengah
        center_layout.addWidget(self.icon_label)
        center_layout.addWidget(self.msg_label)
        center_layout.addWidget(self.sub_label)
        center_layout.addWidget(self.password_input)
        center_layout.addWidget(self.status_label)

        master_layout.addLayout(center_layout)

        # Spacer Bawah untuk menjaga konten tetap berada di tengah layar
        master_layout.addStretch()

        # --- POJOK BAWAH KANAN: TOMBOL SHUTDOWN (IKON ONLY) ---
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addStretch()  # Dorong tombol ke paling kanan

        self.btn_shutdown = QPushButton()
        self.btn_shutdown.setIcon(render_svg_icon(SHUTDOWN_SVG, size=25))
        self.btn_shutdown.setIconSize(QSize(25, 25))
        self.btn_shutdown.setToolTip("Matikan Komputer")
        self.btn_shutdown.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shutdown.setFixedSize(48, 48)  # Ukuran tombol ikon lingkaran
        self.btn_shutdown.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
                border-radius: 24px;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:pressed {
                background-color: #991b1b;
            }
        """)
        self.btn_shutdown.clicked.connect(self.handle_shutdown)
        bottom_bar_layout.addWidget(self.btn_shutdown)

        # Tambahkan bottom_bar ke bagian paling bawah master_layout
        master_layout.addLayout(bottom_bar_layout)

        self.setLayout(master_layout)

        # Tampilkan Fullscreen SETELAH Layout Siap
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.password_input.setFocus()

    def handle_shutdown(self):
        """Mematikan komputer secara langsung saat tombol shutdown di klik."""
        try:
            if platform.system() == "Windows":
                os.system("shutdown /s /t 0")
            else:
                os.system("shutdown -h now")
        except Exception as e:
            print(f"[!] Gagal mengeksekusi shutdown: {e}")

    def handle_unlock_request(self):
        """Memproses permintaan buka kunci saat tombol Enter ditekan."""
        entered_pass = self.password_input.text().strip()

        if not entered_pass:
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
            self.status_label.setText("Kata sandi tidak boleh kosong!")
            return

        self.status_label.setStyleSheet("color: #38bdf8; font-size: 13px;")
        self.status_label.setText("Memverifikasi kata sandi...")

        # Jalankan emit ke server via Async Loop
        if self.sio_client and self.sio_client.connected:
            asyncio.create_task(self.send_unlock_emit(entered_pass))
        else:
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
            self.status_label.setText("Gagal: Tidak terhubung ke server!")

    async def send_unlock_emit(self, password: str):
        """Mengirimkan event Socket.IO ke server untuk memverifikasi kata sandi."""
        try:
            # Mengirimkan permintaan verifikasi ke server dengan timeout 5 detik
            res = await self.sio_client.call( # type: ignore
                "verify_unlock_password",
                {"device_id": self.device_id, "password": password},
                timeout=5.0
            )
            print(f"[DEBUG] Hasil verifikasi server: {res}", flush=True)

            if res and res.get("success"):
                self.status_label.setStyleSheet("color: #4ade80; font-size: 13px;")
                self.status_label.setText("Kata sandi benar! Membuka kunci...")
                # Catatan: Server akan memancarkan event command "unlock" yang akan menutup GUI ini
            else:
                self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
                self.status_label.setText(res.get("message", "Kata sandi salah!"))
                self.password_input.clear()
        except Exception as e:
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
            self.status_label.setText("Kata sandi salah, coba lagi.")
            print(f"[ERROR] Gagal memverifikasi kata sandi: {e}", flush=True)
            self.password_input.clear()

    def closeEvent(self, event): # type: ignore
        # Kembalikan fungsi keyboard saat di-unlock
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