import asyncio
import base64
import os
from dotenv import load_dotenv
import psutil
import socket
import sys
import threading
import aiohttp
from agent_logger import log_error, log_info
from command_handler import (
    execute_open_url,
    execute_ota_update,
    execute_restart,
    execute_shutdown,
    handle_file_chunk,
    run_macro_worker,
)
from config_gui import open_config_gui
from config_manager import load_config
from gui_overlay import LockScreenWidget, show_popup_message
from PyQt6.sip import isdeleted
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop  # Library penyatu Qt & Asyncio
import socketio
from telemetry import capture_screen_bytes, get_system_telemetry
import ctypes
import os
import subprocess
import winreg


# --- KONFIGURASI SOCKET.IO CLIENT ---
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
IS_LOCKED = False

# Config In-Memory (Akan diperbarui jika server mengirimkan event update_config)
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

# --- EXTRACT UNIQUE DEVICE ID ---
def get_c_drive_serial() -> str:
    """Fallback 2: Mengambil Volume Serial Number dari Drive C: via Windows API (ctypes)."""
    try:
        volume_serial_number = ctypes.c_ulong()
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"),
            None,
            0,
            ctypes.byref(volume_serial_number),
            None,
            None,
            None,
            0,
        )
        return f"VOL-{hex(volume_serial_number.value)[2:].upper()}"
    except Exception:
        return ""

def get_system_uuid() -> str:
    """Fallback 1: Mengambil System UUID dari BIOS/Motherboard via PowerShell CIM."""
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"'
        output = subprocess.check_output(cmd, shell=True, timeout=3).decode().strip()
        if output and "00000000" not in output:
            return output
    except Exception:
        pass
    return ""

def get_hardware_id() -> str:
    """Mengekstrak ID Unik Perangkat dengan hirarki fallback yang persistent:

    1. MachineGuid (Windows Registry) -> Paling disarankan
    2. System/Motherboard UUID (BIOS) -> Fallback Hardware
    3. Volume Serial Number (Drive C:) -> Fallback Storage
    """
    # 1. Coba MachineGuid Registry
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if machine_guid:
            return str(machine_guid).strip()
    except Exception:
        pass

    # 2. Fallback 1: Motherboard / System UUID
    bios_uuid = get_system_uuid()
    if bios_uuid:
        return bios_uuid

    # 3. Fallback 2: Volume Serial Drive C:
    drive_serial = get_c_drive_serial()
    if drive_serial:
        return drive_serial

    # 4. Fallback Terakhir: Standar Hostname (jika semua API Windows di-block)
    return f"HOST-{os.getenv('COMPUTERNAME', 'UNKNOWN')}"

DEVICE_ID = get_hardware_id()
# --- SOCKET.IO EVENT HANDLERS ---
@sio.event
async def connect():
    msg = f"[+] Terhubung ke Server Guru sebagai {PC_NAME}"
    print(msg, flush=True)
    log_info(msg)

    try:
        await asyncio.wait_for(
            sio.emit("register_student", {"hostname": PC_NAME, "device_id": DEVICE_ID}), timeout=3.0
        )
        log_info("[+] Berhasil mengirim event register_student ke server.")
    except Exception as e:
        log_error("Gagal mengirim event register_student", exc=e)


@sio.event
async def disconnect():
    msg = "[!] Terputus dari Server Guru. Menunggu auto-reconnect..."
    print(msg, flush=True)
    log_info(msg)

@sio.event
async def connect_error(data):
    msg = f"[!] Gagal terhubung ke server SocketIO: {data}"
    print(msg, flush=True)
    log_error(msg)


@sio.on("update_config") # type: ignore
async def on_update_config(data):
    """Menerima konfigurasi dinamis dari Server RAM."""
    global AGENT_CONFIG
    msg = f"[*] Menerima update_config dari server: {data}"
    print(msg, flush=True)
    log_info(msg)

    if "grid" in data:
        AGENT_CONFIG["grid"] = {
            "quality": data["grid"]["quality"],
            "scale": tuple(data["grid"]["scale"]),
            "interval": float(data["grid"]["interval"]),
        }

    if "fullscreen" in data:
        AGENT_CONFIG["fullscreen"] = {
            "quality": data["fullscreen"]["quality"],
            "scale": tuple(data["fullscreen"]["scale"]),
            "interval": float(data["fullscreen"]["interval"]),
        }
        

@sio.on("command")  # type: ignore
async def on_command(data):
    global lock_widget, CURRENT_MODE, IS_LOCKED
    print(f"[*] Perintah diterima: {data}", flush=True)
    log_info(f"[COMMAND RECEIVED] {data}")

    action = data.get("action")

    if action == "shutdown":
        log_info("[COMMAND] Mematikan komputer...")
        execute_shutdown()

    elif action == "restart":
        log_info("[COMMAND] Merestart komputer...")
        execute_restart()

    elif action == "open_url":
        url = data.get("url")
        log_info(f"[COMMAND] Membuka URL: {url}")
        execute_open_url(url)

    elif action == "message":
        text = data.get("text")
        log_info(f"[COMMAND] Menampilkan pesan popup: {text}")
        show_popup_message("Pesan dari Guru", text)

    elif action == "lock":
        log_info("[COMMAND] Mengunci layar...")
        IS_LOCKED = True

        if lock_widget is not None and not isdeleted(lock_widget):
            lock_widget.showFullScreen()
            lock_widget.raise_()
            lock_widget.activateWindow()
        else:
            print("[*] Mengunci layar siswa...", flush=True)
            lock_widget = LockScreenWidget(
                data.get("message", "DIKUNCI OLEH GURU"), 
                sio_client=sio,
                device_id=DEVICE_ID
            )

    elif action == "unlock":
        log_info("[COMMAND] Membuka kunci layar.")
        IS_LOCKED = False
        lock_widget = safe_cleanup_widget(lock_widget)
        print("[*] Layar siswa dibuka.", flush=True)

    elif action == "set_mode":
        CURRENT_MODE = data.get("mode", "grid")
        log_info(f"[COMMAND] Mode diubah ke: {CURRENT_MODE}")

    elif action == "file_chunk":
        log_info(f"[COMMAND] Menerima file chunk: {data.get('filename')}")
        handle_file_chunk(
            data.get("filename"), data.get("chunk"), data.get("append", True)
        )

    elif action == "ota_update":
        update_url = data.get("url")
        if update_url:
            msg = f"[*] Mengunduh pembaruan OTA dari: {update_url}"
            print(msg, flush=True)
            log_info(msg)
            asyncio.create_task(download_and_apply_ota(update_url))

    elif action == "execute_macro":
        events = data.get("events", [])
        if not events:
            return
        log_info(f"[COMMAND] Mengeksekusi makro keyboard/mouse ({len(events)} events)...")
        macro_thread = threading.Thread(
            target=run_macro_worker, args=(events,), daemon=True
        )
        macro_thread.start()


# --- CONNECTOR LOOPS ---
async def connect_with_retry():
    while True:
        if not sio.connected:
            try:
                log_info(f"[*] Mencoba terhubung ke server SocketIO: {SERVER_URL}")
                print(
                    f"[*] Mencoba terhubung ke server SocketIO: {SERVER_URL}",
                    flush=True,
                )
                await sio.connect(
                    SERVER_URL,
                    transports=["websocket", "polling"],
                    socketio_path="/socket.io",
                )
            except Exception as e:
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


async def send_telemetry_loop():
    while True:
        try:
            mode_key = "grid" if CURRENT_MODE == "grid" else "fullscreen"
            cfg = AGENT_CONFIG.get(mode_key, AGENT_CONFIG["grid"])

            if sio.connected:
                process = psutil.Process(os.getpid())
                ram_usage_mb = process.memory_info().rss / (1024 * 1024)

                telemetry_data = get_system_telemetry()
                payload = {
                    "telemetry": telemetry_data,
                    "image": None,
                    "device_id": DEVICE_ID,
                }

                if not IS_LOCKED:
                    screen_bytes = capture_screen_bytes(
                        quality=cfg["quality"], scale=cfg["scale"]
                    )
                    image_b64 = base64.b64encode(screen_bytes).decode("utf-8")
                    payload["image"] = image_b64

                await asyncio.wait_for(
                    sio.emit("student_frame", payload), timeout=7.0
                )

                print(
                    f"[+] Mengirim Frame ({mode_key.upper()}) | RAM: {ram_usage_mb:.2f} MB | CPU: {telemetry_data.get('cpu')}% | Size: {len(screen_bytes)} bytes",
                    flush=True,
                )
                # Gunakan interval dinamis dari AGENT_CONFIG saat online
                await asyncio.sleep(cfg["interval"])
            else:
                # Jeda 2 detik saat offline agar tidak membebani CPU
                await asyncio.sleep(2.0)

        except asyncio.TimeoutError:
            msg = "[!] TIMEOUT: Server tidak merespon pengiriman frame. Paksa reset socket..."
            print(msg, flush=True)
            log_error(msg)
            try:
                await sio.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2)

        except Exception as e:
            print(f"[!] Error pada telemetry loop: {e}", flush=True)
            log_error("Error pada telemetry loop", exc=e)
            await asyncio.sleep(2)


async def download_and_apply_ota(download_url: str):
    """Mengunduh file .exe baru di latar belakang lalu mengeksekusi OTA update."""
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    new_exe_bytes = await response.read()
                    msg = f"[+] Download OTA selesai ({len(new_exe_bytes)} bytes). Memulai update..."
                    print(msg, flush=True)
                    log_info(msg)

                    if sio.connected:
                        await sio.disconnect()

                    execute_ota_update(new_exe_bytes)
                else:
                    msg = f"[!] Gagal mengunduh OTA: HTTP status {response.status}"
                    print(msg, flush=True)
                    log_error(msg)
    except Exception as e:
        print(f"[!] Error saat mengunduh OTA: {e}", flush=True)
        log_error("Error saat mengunduh OTA", exc=e)


async def main():
    global SERVER_URL
    log_info("=== WATCHERS AGENT CLIENT STARTED ===")

    # Muat konfigurasi dari %ProgramData%
    config = load_config()
    print(f"[*] Konfigurasi dimuat dari {config}", flush=True)
    SERVER_URL = config.get("SERVER_URL")
    print(f"[*] Menggunakan SERVER_URL: {SERVER_URL}", flush=True)

    print(f"[*] Menghubungkan ke Server: {SERVER_URL}")
    await asyncio.gather(connect_with_retry(), send_telemetry_loop())


if __name__ == "__main__":
    # 1. Mode GUI Pengaturan Server (Jalankan secara synchronous tanpa qasync)
    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True) # Izinkan aplikasi keluar saat jendela ditutup
        open_config_gui()
        sys.exit(0)

    # 2. Mode Agent Background Normal
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        try:
            loop.run_until_complete(main())
        except (KeyboardInterrupt, SystemExit):
            print("\n[*] Aplikasi dihentikan secara aman.")
            log_info("[*] Aplikasi dihentikan secara aman.")