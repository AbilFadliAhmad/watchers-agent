import sys
from config_manager import load_config, restart_process, save_config
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ConfigWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Watchers Agent - Pengaturan Server")
        self.setFixedSize(450, 240)

        # Styling Global Dialog (Slate Dark Theme)
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- HEADER (IKON + JUDUL & DESKRIPSI) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_label = QLabel("⚙️")
        icon_label.setStyleSheet("font-size: 28px;")

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_label = QLabel("Pengaturan Server Watchers")
        title_label.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #ffffff;"
        )

        info_label = QLabel("Masukkan URL Dashboard Server yang aktif:")
        info_label.setStyleSheet("font-size: 12px; color: #94a3b8;")

        title_box.addWidget(title_label)
        title_box.addWidget(info_label)

        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # --- INPUT URL SERVER ---
        self.url_input = QLineEdit()
        self.url_input.setText(self.config_data.get("SERVER_URL", ""))
        self.url_input.setPlaceholderText("https://contoh-server.com")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1;
                background-color: #0f172a;
            }
        """)
        layout.addWidget(self.url_input)

        layout.addStretch()

        # --- TOMBOL AKSI ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Tombol Batal
        btn_cancel = QPushButton("Batal")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                padding: 9px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
        """)
        btn_cancel.clicked.connect(self.close)

        # Tombol Simpan
        btn_save = QPushButton("Simpan")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: #ffffff;
                border: none;
                padding: 9px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
            QPushButton:pressed {
                background-color: #3730a3;
            }
        """)
        btn_save.clicked.connect(self.handle_save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Fokuskan kursor secara otomatis ke input URL saat jendela terbuka
        self.url_input.setFocus()
        self.url_input.selectAll()

    def handle_save(self):
        new_url = self.url_input.text().strip()
        if not new_url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self,
                "URL Tidak Valid",
                "URL Server harus diawali dengan http:// atau https://",
            )
            return

        self.config_data["SERVER_URL"] = new_url
        save_config(self.config_data)

        QMessageBox.information(
            self,
            "Berhasil",
            "Pengaturan disimpan. WatchersAgent akan merekonfigurasi ulang sekarang.",
        )
        self.close()
        restart_process()


def open_config_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    window = ConfigWindow()
    window.show()
    app.exec() # Menjalankan Qt Loop standar untuk GUI Config