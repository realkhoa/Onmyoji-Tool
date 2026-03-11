import os
import shutil
import subprocess
import re
import sys

def get_next_version(releases_dir="releases"):
    if not os.path.exists(releases_dir):
        return "0.0.1"
    
    versions = []
    for d in os.listdir(releases_dir):
        m = re.match(r'^v(\d+)\.(\d+)\.(\d+)$', d)
        if m:
            versions.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            
    if not versions:
        return "0.0.1"
        
    v = max(versions)
    return f"{v[0]}.{v[1]}.{v[2]+1}"

def build_app():
    version = get_next_version()
    tag = f"v{version}"
    print(f"Building version: {tag}")
    
    release_dir = os.path.join("releases", tag)
    os.makedirs(release_dir, exist_ok=True)
    
    # Chạy PyInstaller đóng gói thành 1 file .exe duy nhất (--onefile) ẩn console (--windowed)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--add-data", f"dsl;dsl",
        "--add-data", f"images;images",
        "--name", "OnmyojiBot",
        "main.py"
    ]
    
    print(f"Running PyInstaller: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    # Copy file .exe ra thư mục release
    exe_path = os.path.join("dist", "OnmyojiBot.exe")
    dest_exe = os.path.join(release_dir, "OnmyojiBot.exe")
    print(f"Copying {exe_path} to {dest_exe}")
    shutil.copy2(exe_path, dest_exe)
        
    print("---------------------------------------------------------")
    print(f"✅ Build SUCCESS! Version {tag} is ready at: {release_dir}")
    print("---------------------------------------------------------")

if __name__ == "__main__":
    build_app()
