import asyncio
import socket
import sys
from qasync import QEventLoop  # <-- Library penyatu Qt & Asyncio
import os
import psutil
import aiohttp
import threading
import base64

from agent_logger import log_info, log_error
from command_handler import (
    execute_open_url,
    execute_ota_update,
    execute_shutdown,
    handle_file_chunk,
    run_macro_worker,
)
from gui_overlay import LockScreenWidget, show_popup_message
from PyQt6.sip import isdeleted
from PyQt6.QtWidgets import QApplication
import socketio
from telemetry import capture_screen_bytes, get_system_telemetry

sio = socketio.AsyncClient(
    ssl_verify=False,
    reconnection=True,  # Aktifkan auto-reconnect bawaan
    reconnection_attempts=0,  # 0 = Coba terus tanpa batas
    reconnection_delay=2,  # Coba lagi setiap 2 detik
    reconnection_delay_max=5,
)
SERVER_URL = "https://agent.tebaslahandev.my.id"
PC_NAME = socket.gethostname()
CURRENT_MODE = "grid"
lock_widget = None
AGENT_CONFIG = {
    "grid": {"quality": 50, "scale": (640, 360), "interval": 5.0},
    "fullscreen": {"quality": 70, "scale": (1280, 720), "interval": 0.066},
}

# --- HELPER FUNCTION ---
def safe_cleanup_widget(widget):
    if widget is not None and not isdeleted(widget):
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            pass
    return None

@sio.event
async def connect():
    print(f"[+] Terhubung ke Server Guru sebagai {PC_NAME}", flush=True)
    try:
        await asyncio.wait_for(
            sio.emit("register_student", {"hostname": PC_NAME}), timeout=3.0
        )
    except Exception as e:
        log_error("Gagal mengirim event register_student", exc=e)

@sio.on("command")
async def on_command(data):
    global lock_widget, CURRENT_MODE
    print(data, 'isi data command') # untuk memantau perintah
    action = data.get("action")

    if action == "shutdown":
        execute_shutdown()

    elif action == "open_url":
        execute_open_url(data.get("url"))

    elif action == "message":
        show_popup_message("Pesan dari Guru", data.get("text"))

    elif action == "lock":
        if lock_widget is not None and not isdeleted(lock_widget):
            lock_widget.showFullScreen()
            lock_widget.raise_()
            lock_widget.activateWindow()
        else:
            print("[*] Mengunci layar siswa...", flush=True)
            lock_widget = LockScreenWidget(
                data.get("message", "DIKUNCI OLEH GURU")
            )

    elif action == "unlock":
        lock_widget = safe_cleanup_widget(lock_widget)
        print("[*] Layar siswa dibuka.", flush=True)

    elif action == "set_mode":
        CURRENT_MODE = data.get("mode", "grid")

    elif action == "file_chunk":
        handle_file_chunk(
            data.get("filename"), data.get("chunk"), data.get("append", True)
        )

    elif action == "ota_update":
        update_url = data.get("url")  # Contoh: "https://agent.tebaslahandev.my.id/downloads/WatchersAgent_v2.exe"
        if update_url:
            print(f"[*] Mengunduh pembaruan OTA dari: {update_url}", flush=True)
            asyncio.create_task(download_and_apply_ota(update_url))

    elif action == "execute_macro":
        # Ambil payload events dari SocketIO
        events = data.get("events", [])
        if not events:
            return

        # WAJIB: Jalankan di Thread Asinkron agar SocketIO tidak Timeout / Disconnect
        macro_thread = threading.Thread(
            target=run_macro_worker, args=(events,), daemon=True
        )
        macro_thread.start()

async def connect_with_retry():
    while True:
        if not sio.connected:
            try:
                log_info(
                    f"[*] Mencoba terhubung ke server SocketIO: {SERVER_URL}"
                )
                print(
                    f"[*] Mencoba terhubung ke server SocketIO: {SERVER_URL}",
                    flush=True,
                )
                await sio.connect(SERVER_URL)
            except Exception as e:
                # Abaikan warning jika SocketIO sedang dalam proses reconnect internal
                err_str = str(e)
                if (
                    "Already connected" not in err_str
                    and "Already connecting" not in err_str
                ):
                    log_error(f"[!] Gagal terhubung ke {SERVER_URL}", exc=e)
                    print(
                        f"[!] Gagal terhubung ke {SERVER_URL}, mencoba lagi...",
                        flush=True,
                    )

        await asyncio.sleep(4)

# 3. Telemetry Loop dengan Timeout Safeguard
async def send_telemetry_loop():
    while True:
        try:
            # Petakan CURRENT_MODE ("grid" / "focus" / "fullscreen") ke AGENT_CONFIG
            mode_key = "grid" if CURRENT_MODE == "grid" else "fullscreen"
            cfg = AGENT_CONFIG.get(mode_key, AGENT_CONFIG["grid"])

            if sio.connected:
                process = psutil.Process(os.getpid())
                ram_usage_mb = process.memory_info().rss / (1024 * 1024)

                telemetry_data = get_system_telemetry()
                screen_bytes = capture_screen_bytes(
                    quality=cfg["quality"], scale=cfg["scale"]
                )

                # KUNCI PERBAIKAN: Ubah bytes menjadi String Base64 yang aman dari error biner
                image_b64 = base64.b64encode(screen_bytes).decode("utf-8")
                payload = {
                    "hostname": PC_NAME,
                    "telemetry": telemetry_data,
                    "image": image_b64,
                }

                # KUNCI PERBAIKAN: Batasi waktu pengiriman maksimal 3.0 detik (Anti-Macet)
                await asyncio.wait_for(
                    sio.emit("student_frame", payload), timeout=7.0
                )

                print(
                    f"[+] Mengirim Frame | RAM: {ram_usage_mb:.2f} MB | CPU: {telemetry_data.get('cpu')}% | Size: {len(screen_bytes)} bytes",
                    flush=True,
                )

            # Gunakan interval dinamis dari AGENT_CONFIG RAM
            await asyncio.sleep(cfg["interval"])

        except asyncio.TimeoutError:
            # Jika server mati/hang di tengah pengiriman, paksakan disconnect
            print(
                "[!] TIMEOUT: Server tidak merespon pengiriman frame. Paksa reset socket...",
                flush=True,
            )
            log_error("[!] Timeout pengiriman frame. Memaksa disconnect.")
            try:
                await sio.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2)

        except Exception as e:
            print(f"[!] Error pada telemetry loop: {e}", flush=True)
            log_error(f"[ERROR]: {e}")
            await asyncio.sleep(2)

async def download_and_apply_ota(download_url: str):
    """Mengunduh file .exe baru di latar belakang lalu mengeksekusi OTA update."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    new_exe_bytes = await response.read()
                    print(f"[+] Download selesai ({len(new_exe_bytes)} bytes). Memulai update...", flush=True)

                    # Tutup koneksi SocketIO secara bersih sebelum keluar
                    if sio.connected:
                        await sio.disconnect()

                    # Eksekusi replace & restart
                    execute_ota_update(new_exe_bytes)
                else:
                    print(f"[!] Gagal mengunduh OTA: HTTP status {response.status}", flush=True)
    except Exception as e:
        print(f"[!] Error saat mengunduh OTA: {e}", flush=True)

async def main():
    # Jalankan pengelola koneksi dan pengirim frame secara berdampingan (Paralel)
    await asyncio.gather(connect_with_retry(), send_telemetry_loop())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        try:
            loop.run_until_complete(main())
        except (KeyboardInterrupt, SystemExit):
            print("\n[*] Aplikasi dihentikan secara aman.")