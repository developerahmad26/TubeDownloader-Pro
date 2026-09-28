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
        if not display:
            # Auto-detect active X11 sockets in /tmp/.X11-unix/
            x11_dir = "/tmp/.X11-unix"
            found_display = None
            if os.path.isdir(x11_dir):
                try:
                    for sock in sorted(os.listdir(x11_dir)):
                        if sock.startswith("X") and sock[1:].isdigit():
                            found_display = f":{sock[1:]}.0"
                            break
                except Exception:
                    pass

            if found_display:
                os.environ["DISPLAY"] = found_display
                print(f"[*] Auto-detected active X11 Display: {found_display}")
            else:
                print("\n" + "=" * 68)
                print("❌ [ERROR] NO GUI DISPLAY FOUND ($DISPLAY environment variable is empty)!")
                print("=" * 68)
                print("TubeDownloader Pro is a graphical desktop application.")
                print("It cannot open in a headless SSH terminal without an X11/RDP display.\n")
                print("📌 How to run on your VPS:")
                print(" 1. Connect to your VPS using Remote Desktop (RDP / XRDP / VNC).")
                print(" 2. Open the Terminal INSIDE your Remote Desktop screen.")
                print(" 3. Run: ./start_yt.sh")
                print("\nIf you are using SSH with X11 forwarding, connect with: ssh -X user@vps_ip")
                print("Or if an RDP session is already running, try running:")
                print("   export DISPLAY=:10.0  (or DISPLAY=:0.0)")
                print("   ./start_yt.sh")
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
