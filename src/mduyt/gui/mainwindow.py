import os
import sys
import json
import threading
import subprocess
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QProgressBar, QLabel, QRadioButton,
                               QComboBox, QButtonGroup, QFileDialog, QMessageBox, QListView,
                               QStyledItemDelegate, QStatusBar, QStyle, QMenu, QDialog, QCheckBox, QSpinBox)
from PySide6.QtCore import Qt, Slot, QSize, QPoint, __version__
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QPalette, QColor, QAction
from src.mduyt.core.downloader import Downloader
from src.mduyt.gui.menubar import MenuBar
from src.mduyt.gui.multipledownloaddialog import MultipleDownloadDialog
from src.mduyt.core.updater import GitHubUpdater
from src.mduyt.utils.version import appversion, appname
from pathlib import Path
from src.mduyt.data.donator import donators

def normalize_path(path):
    return path.replace(os.sep, '/')

def windows_path(path):
    return path.replace('/', '\\')

def get_app_dir():
    """Get application directory"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def load_info():
    """Load info from info.json"""
    try:
        info_path = os.path.join(get_app_dir(), 'info.json')
        if os.path.exists(info_path):
            with open(info_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"appversion": appversion, "ytdlpversion": "Unknown"}

class HoverButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                opacity: 0.7;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                opacity: 1.0;
            }
        """)
        self.setFixedSize(32, 32)

class HistoryItemWidget(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        icon = QIcon(self.get_icon_path(data['file_type']))
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon.pixmap(QSize(32, 32)))
        layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        self.filename_label = QLabel(data['filename'])
        self.filename_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.filename_label)

        self.path_label = QLabel(data['path'])
        self.path_label.setStyleSheet("color: gray;")
        info_layout.addWidget(self.path_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Add "Open File Location" button with hover effect
        self.open_location_button = HoverButton(self)
        self.open_location_button.setIcon(QIcon(":/folder.svg"))
        self.open_location_button.setToolTip("Open File Location")
        self.open_location_button.clicked.connect(lambda: self.open_file_location(data))
        layout.addWidget(self.open_location_button)

        self.setObjectName("historyItem")
        self.filename_label.setObjectName("filenameLabel")
        self.path_label.setObjectName("pathLabel")

    def get_icon_path(self, file_type):
        if file_type == 'Audio':
            return ":/audio.ico"
        elif file_type == 'Video':
            return ":/vid.ico"
        else:
            return ":/file.ico"

    def open_file_location(self, data):
        file_path = os.path.join(data['path'], data['filename'])
        if sys.platform == "win32":
            file_path = windows_path(file_path)
            subprocess.run(['explorer', '/select,', file_path])
            print(f"Opening file location: {file_path}")
        elif sys.platform == "darwin":
            subprocess.run(['open', '-R', file_path])
        else:
            # For Linux, we'll open the folder and try to select the file if possible
            folder_path = os.path.dirname(file_path)
            subprocess.run(['xdg-open', folder_path])


class HistoryDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.alt_color1 = QColor(53, 53, 53)  # Darker gray
        self.alt_color2 = QColor(45, 45, 45)  # Slightly lighter gray
        self.update_colors()

    def update_colors(self):
        palette = QApplication.palette()
        base_color = palette.color(QPalette.ColorRole.Base)
        if base_color.lightness() < 128:  # Dark theme
            self.alt_color1 = base_color.darker(110)
            self.alt_color2 = base_color.darker(120)
        else:  # Light theme
            self.alt_color1 = base_color.darker(105)
            self.alt_color2 = base_color.darker(110)

    def paint(self, painter, option, index):
        if index.row() % 2 == 0:
            painter.fillRect(option.rect, self.alt_color1)
        else:
            painter.fillRect(option.rect, self.alt_color2)

        if not self.parent().indexWidget(index):
            data = index.data(Qt.UserRole)
            if data:
                widget = HistoryItemWidget(data, self.parent())
                self.parent().setIndexWidget(index, widget)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(42, 130, 218))

    def sizeHint(self, option, index):
        return QSize(0, 50)

class DeleteConfirmationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Item")
        self.setFixedSize(400, 100)

        layout = QVBoxLayout(self)

        # Message
        message_label = QLabel("Are you sure you want to delete this item from the history?")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Checkbox
        self.permanent_delete_checkbox = QCheckBox("Delete file permanently")
        layout.addWidget(self.permanent_delete_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Yes")
        self.no_button = QPushButton("No")
        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        layout.addLayout(button_layout)

        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(self.reject)

# class DownloadSignals(QObject):
#     file_downloaded = Signal(str, str, str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(appname)
        self.setFixedSize(800, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowIcon(QIcon(":/app.ico"))
        self.setMenuBar(MenuBar(self))
        option_layout = QHBoxLayout()

        self.current_version = appversion  # Replace with your actual current version
        self.updater = GitHubUpdater(self.current_version)
        self.updater.signals.update_available.connect(self.on_update_available)
        self.updater.signals.update_progress.connect(self.on_update_progress)
        self.updater.signals.update_completed.connect(self.on_update_completed)
        self.updater.signals.update_error.connect(self.on_update_error)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Youtube Video/Audio URL (other platform is auto video resolution download)")
        url_layout.addWidget(self.url_input)
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        url_layout.addWidget(self.download_button)
        layout.addLayout(url_layout)

        option_layout = QHBoxLayout()

        # Video options
        self.video_radio = QRadioButton("Video:")
        option_layout.addWidget(self.video_radio)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720", "1080", "1440", "2160", "best"])
        option_layout.addWidget(self.resolution_combo)

        self.fps_checkbox = QCheckBox("FPS:")
        option_layout.addWidget(self.fps_checkbox)

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["30", "60", "auto"])
        option_layout.addWidget(self.fps_combo)

        # Audio options
        self.audio_radio = QRadioButton("Audio:")
        option_layout.addWidget(self.audio_radio)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["wav", "mp3", "m4a", "flac"])
        option_layout.addWidget(self.format_combo)

        # Group radio buttons
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.video_radio)
        self.button_group.addButton(self.audio_radio)
        self.video_radio.setChecked(True)

        # Thumbnail checkbox
        self.thumbnail_checkbox = QCheckBox("Download with thumbnail")
        option_layout.addWidget(self.thumbnail_checkbox)


        # Add a checkbox for playlist download
        self.playlist_checkbox = QCheckBox("Download as playlist")
        option_layout.addWidget(self.playlist_checkbox)

        option_layout.addStretch()
        layout.addLayout(option_layout)
       
        # Add stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        url_layout.addWidget(self.stop_button)

        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Download folder:")
        folder_layout.addWidget(self.folder_label)
        self.folder_path = QLineEdit()
        self.folder_path.setText(normalize_path(os.path.expanduser("~/Downloads")))
        folder_layout.addWidget(self.folder_path)
        self.folder_button = QPushButton("Browse")
        self.folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_button)
        layout.addLayout(folder_layout)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Developed by Nawapon Boonjua")

        self.history_model = QStandardItemModel()
        self.history_list = QListView()
        self.history_list.setModel(self.history_model)
        self.history_list.setItemDelegate(HistoryDelegate(self.history_list))
        self.history_list.setUniformItemSizes(False)
        self.history_list.setSpacing(2)
        self.history_list.doubleClicked.connect(self.open_file)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        self.history_list.setStyleSheet("""
            QListView {
                background-color: palette(base);
                border: none;
            }
            QListView::item {
                border: none;
                padding: 2px;
            }
            QListView::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        layout.addWidget(self.history_list)

        self.clear_history_button = QPushButton("Clear History")
        self.clear_history_button.clicked.connect(self.clear_history)
        layout.addWidget(self.clear_history_button)

        self.downloader = Downloader()
        self.downloader.signals.progress.connect(self.update_progress)
        self.downloader.signals.file_downloaded.connect(self.add_to_history)
        self.downloader.signals.finished.connect(self.download_finished)
        self.downloader.signals.error.connect(self.show_error)

        # Add a label for playlist progress
        self.playlist_progress_label = QLabel()
        layout.addWidget(self.playlist_progress_label)

        # Connect signals
        self.video_radio.toggled.connect(self.toggle_options)
        self.audio_radio.toggled.connect(self.toggle_options)
        self.fps_checkbox.stateChanged.connect(self.toggle_fps_combo)

        # Initial state
        self.toggle_options()
        self.toggle_fps_combo()

        self.load_history()

        # Connect text change event
        self.url_input.textChanged.connect(self.check_url)

    def check_url(self):
        url = self.url_input.text()
        if "youtube.com" in url or "youtu.be" in url:
            # Enable resolution and fps combo if YouTube URL
            self.resolution_combo.setEnabled(True)
            self.fps_combo.setEnabled(True)
        else:
            # Disable if it's not a YouTube URL
            self.resolution_combo.setEnabled(False)
            self.fps_combo.setEnabled(False)


    def toggle_options(self):
        is_video = self.video_radio.isChecked()
        self.resolution_combo.setEnabled(is_video)
        self.fps_checkbox.setEnabled(is_video)
        self.fps_combo.setEnabled(is_video and self.fps_checkbox.isChecked())
        self.format_combo.setEnabled(not is_video)

    def toggle_fps_combo(self):
        self.fps_combo.setEnabled(self.fps_checkbox.isChecked() and self.video_radio.isChecked())

    def open_multiple_download_dialog(self):
        dialog = MultipleDownloadDialog(self)
        dialog.start_downloads.connect(self.handle_multiple_downloads)
        dialog.exec()

    def handle_multiple_downloads(self, urls):
        for url in urls:
            # Here you would typically add each URL to your download queue
            # For demonstration, we'll just print the URLs
            print(f"Queued for download: {url}")

    def open_downloads_folder(self):
        folder_path = self.folder_path.text()
        if os.path.exists(folder_path):
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", folder_path])
            else:
                subprocess.call(["xdg-open", folder_path])
        else:
            QMessageBox.warning(self, "Error", "Downloads folder does not exist.")

    def setup_encoding_options(self, layout):
        encoding_layout = QHBoxLayout()

        self.encoding_checkbox = QCheckBox("Custom Encoding")
        encoding_layout.addWidget(self.encoding_checkbox)

        self.encoding_method_combo = QComboBox()
        self.encoding_method_combo.addItems(["x264", "qsv (h264)", "qsv (hevc)", "nvenc (h264)", "nvenc (hevc)", "amf (h264)", "amf (hevc)"])
        self.encoding_method_combo.setEnabled(False)
        encoding_layout.addWidget(self.encoding_method_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText("medium")
        self.preset_combo.setEnabled(False)
        encoding_layout.addWidget(self.preset_combo)

        self.quality_spinbox = QSpinBox()
        self.quality_spinbox.setRange(0, 51)
        self.quality_spinbox.setValue(23)
        self.quality_spinbox.setEnabled(False)
        encoding_layout.addWidget(self.quality_spinbox)

        self.encoding_checkbox.stateChanged.connect(self.toggle_encoding_method)

        layout.addLayout(encoding_layout)

    def get_encoding_command(self, preset="medium", quality=23):
        if not self.encoding_checkbox.isChecked():
            return None
        
        encoding_method = self.encoding_method_combo.currentText()
        
        # Define a dictionary of encoding methods and their corresponding commands
        encoding_commands = {
            "x264": f"-c:v libx264 -preset {preset} -crf {quality}",
            "qsv (h264)": f"-c:v h264_qsv -preset {preset} -global_quality {quality}",
            "qsv (hevc)": f"-c:v hevc_qsv -preset {preset} -global_quality {quality}",
            "nvenc (h264)": f"-c:v h264_nvenc -preset p{preset[0]} -cq {quality}",
            "nvenc (hevc)": f"-c:v hevc_nvenc -preset p{preset[0]} -cq {quality}",
            "amf (h264)": f"-c:v h264_amf -quality {preset} -qp_i {quality} -qp_p {quality} -qp_b {quality}",
            "amf (hevc)": f"-c:v hevc_amf -quality {preset} -qp_i {quality} -qp_p {quality} -qp_b {quality}"
        }
        
        return encoding_commands.get(encoding_method, None)

    def toggle_encoding_method(self, state):
        print(f"Toggle encoding method called. State: {state}")
        is_checked = state == 2  # Qt.Checked is equal to 2
        print(f"Is checked: {is_checked}")
        self.encoding_method_combo.setEnabled(is_checked)
        self.preset_combo.setEnabled(is_checked)
        self.quality_spinbox.setEnabled(is_checked)
        print(f"Combo box enabled: {self.encoding_method_combo.isEnabled()}")

    def show_preferences(self):
        # Implement preferences dialog
        QMessageBox.information(self, "Preferences", "Preferences dialog not implemented yet.")

    def load_info():
        """Load info from info.json"""
        try:
            info_path = os.path.join(get_app_dir(), 'info.json')
            if os.path.exists(info_path):
                with open(info_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"appversion": "1.0.0", "ytdlpversion": "Unknown"}


    def show_about_dialog(self):

        # Create the donator text with each name on a new line, wrapped in <b> tags for bold
        donator_text = "<br>".join([f"{donator}" for donator in donators])
        appname = "MDU YouTube Downloader"
        info = load_info()
        ytdlp_version = info.get('ytdlpversion', 'Unknown')


        # Prepare the message box content using HTML formatting
        about_message = (
            f"<b>{appname}</b><br>"
            f"<b>Version</b> {appversion}<br>"
            f"<b>Developed by</b> Nawapon Boonjua<br><br>"
            f"<b>Qt Version:</b> {__version__}<br>"
            f"<b>Python Version:</b> {sys.version}<br>"
            f"<b>yt-dlp version:</b> {ytdlp_version}<br><br>"
            f"<b>OS:</b> {platform.platform()}<br><br>"
            f"<b>Donators:</b><br>"  # Bold Donators title and list
            f"{donator_text}"
        )

        # Show the message box
        QMessageBox.about(self, f"About {appname}", about_message)

    def check_for_updates(self):
        self.statusBar.showMessage("Checking for updates...")
        threading.Thread(target=self._check_for_updates_thread, daemon=True).start()

    def _check_for_updates_thread(self):
        release = self.updater.check_for_updates()
        if release:
            self.statusBar.showMessage(f"Update available: {release['tag_name']}")
        else:
            self.statusBar.showMessage("No updates available")

    def on_update_available(self, version):
        reply = QMessageBox.question(self, "Update Available",
                                     f"A new version ({version}) is available. Do you want to update?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.start_update()

    def start_update(self):
        self.statusBar.showMessage("Downloading update...")
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _update_thread(self):
        release = self.updater.check_for_updates()
        if release:
            self.updater.download_and_install_update(release)

    def on_update_progress(self, progress):
        self.statusBar.showMessage(f"Updating: {progress}%")

    def on_update_completed(self):
        QMessageBox.information(self, "Update Completed",
                                "The update has been installed. Please restart the application.")
        self.statusBar.showMessage("Update completed")

    def on_update_error(self, error):
        QMessageBox.critical(self, "Update Error", f"An error occurred during the update: {error}")
        self.statusBar.showMessage("Update failed")



    @Slot()
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.folder_path.setText(normalize_path(folder))

    
    @Slot()
    def stop_download(self):
        self.downloader.stop()
        self.status_label.setText("Stopping download...")
        self.stop_button.setEnabled(False)

    @Slot()
    def start_download(self):
        url = self.url_input.text()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a valid URL")
            return

        download_dir = self.normalize_path(self.folder_path.text())
        if not os.path.isdir(download_dir):
            QMessageBox.warning(self, "Error", "Invalid download directory")
            return

        self.download_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Starting download...")
        self.progress_bar.setValue(0)
        self.playlist_progress_label.setText("")

        is_audio = self.audio_radio.isChecked()
        audio_format = self.format_combo.currentText() if is_audio else None
        resolution = self.resolution_combo.currentText() if not is_audio else None
        fps = self.fps_combo.currentText() if (not is_audio and self.fps_checkbox.isChecked()) else None
        is_playlist = self.playlist_checkbox.isChecked()
        with_thumbnail = self.thumbnail_checkbox.isChecked()

        # if title is None:
        #     QMessageBox.warning(self, "Error", "Failed to fetch title. Download will not start.")
        #     self.download_button.setEnabled(True)  # Re-enable the download button
        #     self.stop_button.setEnabled(False)
        #     return

        # Start the download thread
        self.download_thread = threading.Thread(target=self.download_thread_function,
                                                args=(url, is_audio, audio_format, resolution, fps, download_dir,
                                                      is_playlist, with_thumbnail),
                                                daemon=True)
        self.download_thread.start()

    def download_thread_function(self, url, is_audio, audio_format, resolution, fps, download_dir, 
                                 is_playlist, with_thumbnail):
        self.downloader.download(url, is_audio, audio_format, resolution, fps, download_dir, 
                                 is_playlist, with_thumbnail)
    @Slot(float, str, str, str, int, int)
    def update_progress(self, progress, file_size, download_speed, eta, current_item, total_items):
        self.progress_bar.setValue(int(progress))
        status = f"Downloading: {progress:.1f}%"
        if file_size:
            status += f" | Size: {file_size}"
        if download_speed:
            status += f" | Speed: {download_speed}"
        if eta:
            status += f" | ETA: {eta}"
        self.status_label.setText(status)
        
        if total_items > 1:
            self.playlist_progress_label.setText(f"Downloading item {current_item} of {total_items}")
        else:
            self.playlist_progress_label.setText("")


    @Slot(str)
    def show_error(self, error_message):
        self.status_label.setText(f"Error: {error_message}")
        self.download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.playlist_progress_label.setText("")
        QMessageBox.critical(self, "Error", error_message)

    @Slot()
    def download_finished(self):
        self.status_label.setText("Download completed!")
        self.download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.playlist_progress_label.setText("")
        QMessageBox.information(self, "Success", "Download completed successfully!")
        self.progress_bar.setValue(0)

    def toggle_options(self):
        is_video = self.video_radio.isChecked()
        self.resolution_combo.setEnabled(is_video)
        self.fps_combo.setEnabled(is_video)
        self.format_combo.setEnabled(not is_video)

    @Slot(str, str, str)
    def add_to_history(self, filename, file_path, file_type):
        item = QStandardItem()

        # Normalize the filename and path
        normalized_filename = self.normalize_unicode(filename)
        normalized_path = self.normalize_unicode(file_path)

        # Ensure file_type is correct
        if file_type == "Unknown":
            file_type = self.determine_file_type(normalized_filename)

        item_data = {
            'filename': normalized_filename,
            'path': normalized_path,
            'file_type': file_type
        }

        item.setData(item_data, Qt.UserRole)
        self.history_model.insertRow(0, item)
        self.save_history()

    def determine_file_type(self, filename):
        if any(filename.lower().endswith(ext) for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']):
            return "Video"
        elif any(filename.lower().endswith(ext) for ext in ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']):
            return "Audio"
        else:
            return "Unknown"

    def normalize_unicode(self, path):
        return Path(path).as_posix()
    
    def normalize_path(self, path):
        # Normalizes path based on the OS, ensuring compatibility with various encodings
        if sys.platform == "win32":
            return path.replace('\\', '/')
        return path

    def save_history(self):
            history_data = []
            for row in range(self.history_model.rowCount()):
                item = self.history_model.item(row)
                item_data = item.data(Qt.UserRole)
                history_data.append(item_data)

            with open('history.json', 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

    def load_history(self):
        try:
            with open('history.json', 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            for item_data in history_data:
                item = QStandardItem()
                item.setData(item_data, Qt.UserRole)
                self.history_model.appendRow(item)
        except FileNotFoundError:
            pass  # No history file exists yet
    @Slot()
    def clear_history(self):
        reply = QMessageBox.question(self, 'Clear History',
                                     'Are you sure you want to clear the download history?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.history_model.clear()
            if os.path.exists("download_history.json"):
                os.remove("download_history.json")
            self.status_label.setText("History cleared")


    @Slot(QPoint)
    def show_context_menu(self, position):
        index = self.history_list.indexAt(position)
        if not index.isValid():
            return

        menu = QMenu(self)
        open_action = QAction("Open File", self)
        open_action.triggered.connect(lambda: self.open_file(index))
        menu.addAction(open_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.delete_item(index))
        menu.addAction(delete_action)

        menu.exec_(self.history_list.viewport().mapToGlobal(position))

    def open_file(self, index):
        data = index.data(Qt.UserRole)
        if data:
            file_path = normalize_path(os.path.join(data['path'], data['filename']))
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", file_path])
            else:
                subprocess.call(["xdg-open", file_path])

    def delete_item(self, index):
        dialog = DeleteConfirmationDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = index.data(Qt.UserRole)
            self.history_model.removeRow(index.row())
            self.save_history()
            self.status_label.setText("Item deleted from history")

            if dialog.permanent_delete_checkbox.isChecked():
                file_path = os.path.join(data['path'], data['filename'])
                try:
                    os.remove(file_path)
                    self.status_label.setText("Item and file deleted permanently")
                except OSError as e:
                    QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    # Define dark and light palettes
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    light_palette = QPalette()
    light_palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(240, 240, 240))
    light_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.Button, Qt.GlobalColor.white)
    light_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    light_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    light_palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
    light_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    # Function to set the theme
    def set_theme(is_dark):
        if is_dark:
            app.setPalette(dark_palette)
            app.setStyleSheet("""
                QToolTip {
                    color: #ffffff;
                    background-color: #2a82da;
                    border: 1px solid white;
                }
                QWidget {
                    font-size: 11px;
                }
                QListView::item:selected {
                    background-color: #2a82da;
                }
            """)
        else:
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("""
                QToolTip {
                    color: #000000;
                    background-color: #f0f0f0;
                    border: 1px solid black;
                }
                QWidget {
                    font-size: 11px;
                }
                QListView::item:selected {
                    background-color: #0078d7;
                }
            """)

    # Auto-detect system theme
    if hasattr(QStyleFactory, 'qt_mac_set_native_theme'):
        # macOS
        from Foundation import NSUserDefaults
        is_dark = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark"
    elif sys.platform == "win32":
        # Windows
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            is_dark = value == 0
        except FileNotFoundError:
            is_dark = False
    else:
        # Linux and others (default to light theme)
        is_dark = False

    # Set the detected theme
    set_theme(is_dark)

    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
