"""
Total Commander Clone - Modern Dual-Pane File Manager
Entry point for the application.
"""

import sys
import os
import ctypes

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPalette

from file_manager_app import FileManagerApp
from settings_manager import SettingsManager
from theme import applyTheme
from app_version import APP_VERSION


# ------------------------------------------------------------
# Function: getBasePath
# Purpose: Returns the base directory where the application
#          and its config files reside.
# ------------------------------------------------------------
def getBasePath():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------
# Function: getConfigPath
# Purpose: Returns the directory for settings.json and state.json.
#          When frozen: uses %APPDATA% so settings persist across
#          rebuilds. When dev: uses project directory.
# ------------------------------------------------------------
def getConfigPath():
    if getattr(sys, 'frozen', False):
        if os.name == "nt":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.join(os.path.expanduser("~"), ".config")
        return os.path.join(base, "TotalCommanderClone")
    return os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------
# Function: configureWindowsTaskbarIdentity
# Purpose: Ensures Windows groups this app with a custom
#          AppUserModelID so the taskbar uses app icon identity.
# ------------------------------------------------------------
def configureWindowsTaskbarIdentity():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "TCClone.FileExplorer"
        )
    except Exception:
        pass


# ------------------------------------------------------------
# Function: resolveAppIconPath
# Purpose: Resolves path to file-explorer.ico from common app
#          locations.
# ------------------------------------------------------------
def resolveAppIconPath(base_path):
    candidate_paths = [
        os.path.join(base_path, "file-explorer.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "file-explorer.ico"),
    ]
    for icon_path in candidate_paths:
        if os.path.isfile(icon_path):
            return icon_path
    return ""


# ------------------------------------------------------------
# Function: main
# Purpose: Initializes the application, loads settings,
#          applies the dark theme, and launches the main window.
# ------------------------------------------------------------
def main():
    configureWindowsTaskbarIdentity()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Total Commander Clone")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("TCClone")
    app._system_style_name = app.style().objectName()
    app._system_palette = QPalette(app.palette())

    base_path = getBasePath()
    config_path = getConfigPath()
    if getattr(sys, 'frozen', False) and not os.path.isdir(config_path):
        os.makedirs(config_path, exist_ok=True)
    icon_path = resolveAppIconPath(base_path)
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    settings_manager = SettingsManager(config_path)

    font_size = int(settings_manager.getSetting("font_size", 10))
    applyTheme(app, settings_manager.getSetting("theme_mode", "dark"), font_size)

    window = FileManagerApp(settings_manager)
    if icon_path:
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    exit_code = app.exec_()
    settings_manager.saveAll()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
