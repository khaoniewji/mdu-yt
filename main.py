import sys
import os
import platform
import subprocess
import requests
import json
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt
from src.mduyt.gui.mainwindow import MainWindow
import src.mduyt.gui.resources_rc
from src.mduyt.core.downloader import Downloader
from src.mduyt.utils.version import appversion

def get_app_dir():
    """Get application directory"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def load_info():
    """Load info from info.json"""
    try:
        info_path = os.path.join(get_app_dir(), 'info.json')
        if os.path.exists(info_path):
            with open(info_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"appversion": appversion, "ytdlpversion": None}

def save_info(info):
    """Save info to info.json"""
    try:
        info_path = os.path.join(get_app_dir(), 'info.json')
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=4)
    except Exception:
        pass

def get_local_ytdlp_version():
    """Get local yt-dlp version from info.json"""
    try:
        info = load_info()
        return info.get('ytdlpversion')
    except Exception:
        return None

def get_ytdlp_exe_version():
    """Get version directly from yt-dlp.exe"""
    try:
        ytdlp_path = os.path.join(get_app_dir(), 'bin', 'win', 'yt-dlp.exe')
        
        if not os.path.exists(ytdlp_path):
            return None
            
        result = subprocess.run([ytdlp_path, '--version'], 
                              capture_output=True, text=True)
        version = result.stdout.strip()
        
        # Update version in info.json
        info = load_info()
        info['ytdlpversion'] = version
        save_info(info)
        
        return version
    except Exception:
        return None

def get_latest_ytdlp_version():
    """Get latest yt-dlp version from GitHub"""
    try:
        api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()['tag_name']
    except Exception:
        return None

def download_latest_ytdlp(splash):
    """Download and replace yt-dlp if newer version available"""
    try:
        bin_dir = os.path.join(get_app_dir(), 'bin', 'win')
        os.makedirs(bin_dir, exist_ok=True)
        target_path = os.path.join(bin_dir, 'yt-dlp.exe')

        splash.showMessage("Downloading new yt-dlp version...", 
                         Qt.AlignBottom | Qt.AlignLeft, Qt.white)
        
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get total file size for progress calculation
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    f.write(chunk)
                    
                    # Update progress message with percentage
                    if total_size:
                        progress = (downloaded_size / total_size) * 100
                        splash.showMessage(
                            f"Downloading new yt-dlp version... {progress:.1f}%",
                            Qt.AlignBottom | Qt.AlignLeft, Qt.white
                        )
                        QApplication.processEvents()
        
        return True
    except Exception as e:
        print(f"Download error: {str(e)}")
        return False

def create_default_info():
    """Create default info.json if not exists"""
    if not os.path.exists(os.path.join(get_app_dir(), 'info.json')):
        default_info = {
            "appversion": "1.0.0",
            "ytdlpversion": None
        }
        save_info(default_info)

def initialize_app():
    """Initialize application directories and files"""
    # Create bin/win directory if not exists
    bin_dir = os.path.join(get_app_dir(), 'bin', 'win')
    os.makedirs(bin_dir, exist_ok=True)
    
    # Create default info.json if not exists
    create_default_info()

if __name__ == "__main__":
    # Initialize Qt Application
    qt_app = QApplication(sys.argv)
    qt_app.setStyle("fusion")
    qt_app.setWindowIcon(QIcon("qrc:/icon.ico"))

    # Create and display splash screen
    splash_pix = QPixmap(":/splash_new_3.png")
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    
    # Initialize application
    splash.showMessage("Initializing...", Qt.AlignBottom | Qt.AlignLeft, Qt.white)
    qt_app.processEvents()
    initialize_app()
    
    # Check versions
    splash.showMessage("Checking yt-dlp version...", 
                      Qt.AlignBottom | Qt.AlignLeft, Qt.white)
    qt_app.processEvents()
    
    local_version = get_local_ytdlp_version()
    if local_version is None:
        local_version = get_ytdlp_exe_version()
    
    latest_version = get_latest_ytdlp_version()
    
    # Update if necessary
    if latest_version and (not local_version or local_version != latest_version):
        splash.showMessage(f"Found new version: {latest_version}", 
                          Qt.AlignBottom | Qt.AlignLeft, Qt.white)
        qt_app.processEvents()
        
        if download_latest_ytdlp(splash):
            info = load_info()
            info['ytdlpversion'] = latest_version
            save_info(info)
            splash.showMessage("Update completed successfully!", 
                             Qt.AlignBottom | Qt.AlignLeft, Qt.white)
        else:
            splash.showMessage("Update failed, continuing with current version", 
                             Qt.AlignBottom | Qt.AlignLeft, Qt.white)
        qt_app.processEvents()

    # Load main application
    splash.showMessage("Loading application...", 
                      Qt.AlignBottom | Qt.AlignLeft, Qt.white)
    qt_app.processEvents()
    
    window = MainWindow()

    # Finish splash and show main window
    splash.finish(window)
    window.show()
    
    # Start application
    sys.exit(qt_app.exec())