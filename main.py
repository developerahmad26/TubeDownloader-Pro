"""TubeDownloader Pro — Entry Point.

A professional YouTube video downloader with support for:
- Single video downloads
- Full playlist downloads
- Channel video downloads
- Full customization of quality, naming, selection, and more.

Usage:
    python main.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Auto-switch to dedicated virtual environment if running in system Python on Linux/VPS
if sys.platform != "win32":
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(proj_dir, "venv", "bin", "python")
    if os.path.isfile(venv_py) and os.path.realpath(sys.executable) != os.path.realpath(venv_py):
        os.execv(venv_py, [venv_py] + sys.argv)


def check_environment():
    """Verify system GUI requirements and dependencies before launch."""
    # 1. Check Tkinter (System GUI framework)
    try:
        import tkinter
    except (ImportError, ModuleNotFoundError):
        print("\n" + "=" * 68)
        print("❌ [ERROR] Tkinter GUI framework is not installed on this system!")
        print("=" * 68)
        if sys.platform != "win32":
            print("\nTkinter is required to display the GUI window on Linux / VPS.")
            print("To fix this, run this command in your VPS terminal:")
            print("\n   sudo apt-get update && sudo apt-get install -y python3-tk\n")
        else:
            print("\nPlease reinstall Python from python.org and make sure")
            print("'tcl/tk and IDLE' is checked in the installer.")
        print("=" * 68 + "\n")
        sys.exit(1)

    # 2. Check Display on Linux / Unix systems
    if sys.platform != "win32":
        display = os.environ.get("DISPLAY")
        display_works = False
        if display:
            try:
                t = tkinter.Tk(screenName=display)
                t.destroy()
                display_works = True
            except Exception:
                display_works = False

        if not display_works:
            # Auto-detect active X11 sockets in /tmp/.X11-unix/
            x11_dir = "/tmp/.X11-unix"
            found_display = None
            if os.path.isdir(x11_dir):
                try:
                    candidates = []
                    # Prioritize higher display numbers (common for XRDP :10, :11) then lower
                    for sock in sorted(os.listdir(x11_dir), reverse=True):
                        if sock.startswith("X") and sock[1:].isdigit():
                            candidates.append(f":{sock[1:]}.0")
                            candidates.append(f":{sock[1:]}")
                    for disp in candidates:
                        try:
                            t = tkinter.Tk(screenName=disp)
                            t.destroy()
                            found_display = disp
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

            if found_display:
                os.environ["DISPLAY"] = found_display
                print(f"[*] Auto-detected active working X11 Display: {found_display}")
            else:
                print("\n" + "=" * 68)
                print("❌ [ERROR] NO WORKING GUI DISPLAY FOUND ($DISPLAY is unreachable)!")
                print("=" * 68)
                print("TubeDownloader Pro is a graphical desktop application.")
                print("It requires an active Remote Desktop (RDP / XRDP / VNC) screen.\n")
                print("📌 Kaise solve karein:")
                print(" 1. Apne VPS ko Remote Desktop (RDP / Windows Remote Desktop Connection) se connect karein.")
                print(" 2. RDP screen ke andar Terminal khol kar run karein:")
                print("       ./start.sh")
                print(" 3. Ya Desktop par bane 'TubeDownloader Pro' icon par double-click karein.")
                print("=" * 68 + "\n")
                sys.exit(1)

    # 3. Check Python package dependencies
    required_packages = {
        "yt_dlp": "yt-dlp",
        "customtkinter": "customtkinter",
        "PIL": "Pillow",
        "mutagen": "mutagen",
    }
    missing = []
    for module_name, pip_name in required_packages.items():
        try:
            __import__(module_name)
        except (ImportError, ModuleNotFoundError):
            missing.append(pip_name)

    if missing:
        print("\n" + "=" * 68)
        print("❌ [ERROR] Missing required Python packages!")
        print("=" * 68)
        print(f"Missing: {', '.join(missing)}\n")
        print("Install them all at once by running:")
        print("   pip install -r requirements.txt")
        print("\nOr install individually:")
        print(f"   pip install {' '.join(missing)}")
        print("=" * 68 + "\n")
        sys.exit(1)


def main():
    """Launch the application with crash-safe protection."""
    check_environment()

    try:
        from gui import App

        print("[*] Starting TubeDownloader Pro...")
        app = App()
        app.mainloop()
    except Exception as exc:
        import traceback
        err_msg = traceback.format_exc()
        print("\n" + "=" * 68)
        print("❌ [FATAL ERROR] TubeDownloader Pro failed to launch:")
        print("=" * 68)
        print(err_msg)
        print("=" * 68)

        # Write crash report
        crash_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        try:
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write(err_msg)
            print(f"Crash report written to: {crash_log}")
        except Exception:
            pass

        if sys.stdin.isatty():
            input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
