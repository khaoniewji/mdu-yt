# installer.py
import sys
import os
import shutil
import requests
import winreg
import ctypes
import tempfile
from PySide6.QtWidgets import (QApplication, QMainWindow, QProgressBar, 
                              QLabel, QPushButton, QVBoxLayout, QWidget,
                              QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon
import subprocess
import json
import src.mduyt.gui.resources_rc

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

class GitHubRelease:
    def __init__(self):
        self.api_url = "https://api.github.com/repos/project-mdu/mdu-yt/releases/latest"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }

    def get_latest_release(self):
        try:
            response = requests.get(self.api_url, headers=self.headers)
            response.raise_for_status()
            release_data = response.json()
            
            installer_asset = next(
                (asset for asset in release_data['assets'] 
                 if asset['name'].endswith('.exe')),
                None
            )
            
            if not installer_asset:
                raise Exception("No Windows installer found in release")

            return {
                'version': release_data['tag_name'],
                'name': release_data['name'],
                'description': release_data['body'],
                'download_url': installer_asset['browser_download_url'],
                'size': installer_asset['size'],
                'published_at': release_data['published_at']
            }
        except Exception as e:
            raise Exception(f"Failed to fetch release info: {str(e)}")

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self._is_cancelled = False
        
    def cancel(self):
        self._is_cancelled = True
        
    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    if self._is_cancelled:
                        return
                    
                    downloaded += len(data)
                    f.write(data)
                    if total_size:
                        progress = int((downloaded / total_size) * 100)
                        self.progress.emit(progress)
                        
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))

class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MDU Installer")
        self.setFixedSize(500, 300)
        self.setWindowIcon(QIcon(":/app.ico"))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Version info label
        self.version_label = QLabel("Checking for latest version...")
        self.version_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.version_label)
        
        # Release notes
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("""
            QLabel { 
                background-color: #1e1e1e; 
                padding: 10px; 
                border-radius: 5px;
                border: 1px solid #3e3e3e;
                font-size: 11px;
            }
        """)
        self.notes_label.setMinimumHeight(150)
        layout.addWidget(self.notes_label)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #3add36;
                width: 1px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_installation)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #d43c3c;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 3px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #b13535;
            }
        """)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button, alignment=Qt.AlignCenter)
        
        # Setup paths
        self.app_name = "Media Downloader Utility"
        self.company = "kaoniewji"
        self.install_dir = os.path.join(
            os.environ['LOCALAPPDATA'],
            self.company,
            self.app_name
        )
        
        self.temp_file = os.path.join(tempfile.gettempdir(), 'mdu_setup.exe')
        self.download_thread = None
        
        # Start installation process
        QTimer.singleShot(500, self.fetch_latest_release)

    def fetch_latest_release(self):
        try:
            self.status_label.setText("Checking for latest version...")
            github = GitHubRelease()
            self.release_info = github.get_latest_release()
            
            self.version_label.setText(
                f"Version: {self.release_info['version']}\n"
                f"Released: {self.release_info['published_at'][:10]}"
            )
            
            self.notes_label.setText(self.release_info['description'])
            self.cancel_button.show()
            
            # Continue to installation check
            self.check_existing_installation()
            
        except Exception as e:
            self.handle_error(f"Failed to fetch release info: {str(e)}")

    def check_existing_installation(self):
        try:
            if os.path.exists(self.install_dir):
                reply = QMessageBox.question(
                    self,
                    "Existing Installation",
                    "An existing installation was found. Would you like to uninstall it?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Yes:
                    self.status_label.setText("Uninstalling previous version...")
                    self.uninstall_existing()
                    QTimer.singleShot(500, self.start_installation)
                elif reply == QMessageBox.No:
                    self.start_installation()
                else:
                    self.close()
            else:
                self.start_installation()
                
        except Exception as e:
            self.handle_error(f"Installation check failed: {str(e)}")

    def uninstall_existing(self):
        try:
            self.kill_running_processes()
            self.remove_desktop_shortcut()
            self.remove_registry_entries()
            
            if os.path.exists(self.install_dir):
                shutil.rmtree(self.install_dir, ignore_errors=True)
            
            self.status_label.setText("Previous version uninstalled")
            
        except Exception as e:
            self.handle_error(f"Uninstall failed: {str(e)}")

    def kill_running_processes(self):
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'mdu.exe'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        except:
            pass

    def remove_desktop_shortcut(self):
        try:
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            shortcut_path = os.path.join(desktop, f"{self.app_name}.lnk")
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
        except:
            pass

    def remove_registry_entries(self):
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MDU"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except:
            pass

    def start_installation(self):
        self.status_label.setText("Starting download...")
        self.cancel_button.setEnabled(True)
        
        self.download_thread = DownloadThread(
            self.release_info['download_url'], 
            self.temp_file
        )
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.install_application)
        self.download_thread.error.connect(self.handle_error)
        self.download_thread.start()

    def cancel_installation(self):
        reply = QMessageBox.question(
            self,
            "Cancel Installation",
            "Are you sure you want to cancel the installation?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.download_thread:
                self.download_thread.cancel()
            self.close()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.status_label.setText(f"Downloading... {value}%")

    def install_application(self):
        try:
            self.status_label.setText("Completing installation...")
            os.makedirs(self.install_dir, exist_ok=True)
            self.create_shortcut()
            self.add_to_registry()
            
            if os.path.exists(self.temp_file):
                subprocess.run([self.temp_file], check=True)
            
            self.close()
            
        except Exception as e:
            self.handle_error(str(e))

    def create_shortcut(self):
        try:
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            shortcut_path = os.path.join(desktop, f"{self.app_name}.lnk")
            
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = os.path.join(self.install_dir, "mdu.exe")
            shortcut.IconLocation = os.path.join(self.install_dir, "icon.ico")
            shortcut.save()
            
        except Exception as e:
            print(f"Failed to create shortcut: {e}")

    def add_to_registry(self):
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MDU"
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, self.app_name)
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, 
                                os.path.join(self.install_dir, "uninstall.exe"))
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, 
                                os.path.join(self.install_dir, "icon.ico"))
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, self.company)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, 
                                self.release_info['version'])
                
        except Exception as e:
            print(f"Failed to add registry entries: {e}")

    def handle_error(self, error_msg):
        self.status_label.setText(f"Error: {error_msg}")
        QMessageBox.critical(
            self,
            "Installation Error",
            f"An error occurred during installation:\n{error_msg}"
        )
        self.cancel_button.setEnabled(True)

    def closeEvent(self, event):
        if os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
        event.accept()

if __name__ == "__main__":
    if not is_admin():
        run_as_admin()
        sys.exit()

    app = QApplication(sys.argv)
    app.setStyle("fusion")
    
    window = InstallerWindow()
    window.show()
    
    sys.exit(app.exec())