from PySide6.QtWidgets import QMenuBar, QMenu,QMessageBox,QProgressDialog, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt,QTimer
from env import root
import sys 
import os
import requests
class MenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.create_file_menu()
        self.create_edit_menu()
        self.create_help_menu()

    def create_file_menu(self):
        file_menu = self.addMenu("&File")

        new_download = QAction(QIcon(":/icons/new.png"), "&Add Multiple Download", self)
        new_download.setShortcut("Ctrl+N")
        new_download.triggered.connect(self.parent.open_multiple_download_dialog)
        file_menu.addAction(new_download)

        open_downloads = QAction(QIcon(":/icons/open.png"), "&Open Downloads Folder", self)
        open_downloads.setShortcut("Ctrl+O")
        open_downloads.triggered.connect(self.parent.open_downloads_folder)
        file_menu.addAction(open_downloads)

        file_menu.addSeparator()

        exit_action = QAction(QIcon(":/icons/exit.png"), "E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.parent.close)
        file_menu.addAction(exit_action)

    def create_edit_menu(self):
        edit_menu = self.addMenu("&Edit")

        preferences = QAction(QIcon(":/icons/preferences.png"), "&Preferences", self)
        preferences.setShortcut("Ctrl+P")
        preferences.triggered.connect(self.parent.show_preferences)
        edit_menu.addAction(preferences)

    def create_help_menu(self):
        help_menu = self.addMenu("&Help")

        about_action = QAction(QIcon(":/icons/about.png"), "&About", self)
        about_action.triggered.connect(self.parent.show_about_dialog)
        help_menu.addAction(about_action)

        check_updates = QAction(QIcon(":/icons/update.png"), "Check for &Updates", self)
        check_updates.triggered.connect(self.parent.check_for_updates)
        help_menu.addAction(check_updates)
# def new_download(self):
#     # Implement new download functionality
#     pass

# def open_downloads_folder(self):
#     # Open the downloads folder
#     pass

# def show_preferences(self):
#     # Show preferences dialog
#     pass

# def toggle_history_view(self):
#     # Toggle the visibility of the history view
#     pass

# def show_about_dialog(self):
#     # Show about dialog
#     pass

# def check_for_updates(self):
#     # Check for updates
#     pass