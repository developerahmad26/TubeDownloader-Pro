"""Automated build script for packaging YT Video Downloader Pro into a standalone .exe."""

import os
import shutil
import subprocess
import sys

def build():
    print("[*] Starting PyInstaller build process...")
    
    # Ensure icon exists
    if not os.path.exists("assets/icon.ico"):
        print("[*] Generating premium icon first...")
        from create_icon import create_premium_icon
        create_premium_icon()
        
    ffmpeg_path = shutil.which("ffmpeg") or r"C:\Users\Hammad Khursheed\AppData\Local\Programs\Python\Python312\Scripts\ffmpeg.exe"
    ffprobe_path = shutil.which("ffprobe") or r"C:\Users\Hammad Khursheed\AppData\Local\Programs\Python\Python312\Scripts\ffprobe.exe"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=TubeDownloader Pro",
        "--icon=assets/icon.ico",
        "--add-data=assets;assets",
        "--collect-all=customtkinter",
        "--collect-all=yt_dlp",
        "--collect-all=mutagen",
        "--collect-all=PIL",
    ]
    
    if os.path.exists(ffmpeg_path):
        print(f"[*] Bundling ffmpeg from: {ffmpeg_path}")
        cmd.append(f"--add-binary={ffmpeg_path};.")
    if os.path.exists(ffprobe_path):
        print(f"[*] Bundling ffprobe from: {ffprobe_path}")
        cmd.append(f"--add-binary={ffprobe_path};.")
        
    cmd.append("main.py")
    
    print("[*] Running command:")
    print(" ".join(cmd))
    
    result = subprocess.run(cmd)
    if result.returncode == 0:
        exe_path = os.path.abspath(os.path.join("dist", "TubeDownloader Pro.exe"))
        # Also copy to root directory for easy access
        root_exe = os.path.abspath("TubeDownloader Pro.exe")
        try:
            shutil.copy2(exe_path, root_exe)
        except Exception:
            pass
        print("\n" + "="*60)
        print("[SUCCESS] Standalone EXE created successfully!")
        print(f"Location: {root_exe}")
        if os.path.exists(root_exe):
            size_mb = os.path.getsize(root_exe) / (1024 * 1024)
            print(f"Size: {size_mb:.2f} MB")
        print("="*60 + "\n")
    else:
        print("\n[ERROR] PyInstaller build failed with return code:", result.returncode)
        sys.exit(result.returncode)

if __name__ == "__main__":
    build()
