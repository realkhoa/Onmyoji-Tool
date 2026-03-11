import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadHandler(FileSystemEventHandler):
    def __init__(self, script_name):
        self.script_name = script_name
        self.process = None
        self.last_reload = 0
        self.restart_app()

    def restart_app(self):
        if self.process:
            print(f"\n[HOT RELOAD] File change detected. Restarting {self.script_name}...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        else:
            print(f"[HOT RELOAD] Starting {self.script_name}...")
        
        # Using sys.executable to ensure we use the same python interpreter
        self.process = subprocess.Popen([sys.executable, self.script_name])

    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Filter for relevant files
        if event.src_path.endswith(('.py', '.dsl')):
            # Debounce: avoid multiple restarts within 1 second
            now = time.time()
            if now - self.last_reload > 1.0:
                self.last_reload = now
                self.restart_app()

if __name__ == "__main__":
    target_script = "main.py"
    path = "."
    
    event_handler = ReloadHandler(target_script)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    
    print(f"[HOT RELOAD] Monitoring changes in {path} (recursive)...")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.terminate()
    
    observer.join()
