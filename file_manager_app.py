"""
Total Commander Clone - Main Application Window
Assembles the dual-pane layout, toolbar, menu bar, status bar,
right-click context menus, keyboard shortcuts, and bookmarks.
"""

import os
import subprocess
import platform

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QToolBar, QAction, QStatusBar,
    QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget,
    QMenu, QMessageBox, QInputDialog, QApplication, QLabel,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog,
    QStyle, QTabWidget, QStackedWidget,
)
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QKeySequence, QDesktopServices, QIcon

from file_panel import FilePanel
from file_operations import copyFiles, moveFiles, deleteFiles, renameFile
from batch_rename_dialog import BatchRenameDialog
from bookmarks_panel import BookmarksPanel
from libraries_panel import LibrariesPanel
from library_browser_panel import LibraryBrowserPanel
from library_dialogs import LibraryRootDialog, TagAssignmentDialog
from library_manager import LibraryManager
from settings_manager import SettingsManager
from windows_shell_clipboard import setFileClipboard, getClipboardDropEffect
from app_version import APP_VERSION, APP_NAME, getWindowTitle
from file_properties_dialog import showFileProperties
from settings_dialog import SettingsDialog
from theme import applyTheme


# ============================================================
# Class: FileManagerApp
# Purpose: The main application window. Manages the dual-pane
#          file browser, toolbar, menu bar, keyboard shortcuts,
#          right-click menus, drag-and-drop integration, and
#          settings persistence.
# ============================================================
class FileManagerApp(QMainWindow):

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self._settings = settings_manager
        self._library_manager = LibraryManager(settings_manager)
        self._active_panel = None
        self._clipboard_paths = []
        self._clipboard_mode = None

        self._initWindow()
        self._initStatusBar()
        self._initMenuBar()
        self._initToolBar()
        self._initPanels()
        self._initBottomBar()
        self._initShortcuts()
        self._restoreState()
        self._updateMirrorTooltips()

    # --------------------------------------------------------
    # Method: _initWindow
    # Purpose: Configures window title, geometry, and restores
    #          saved position/size from settings.
    # --------------------------------------------------------
    def _initWindow(self):
        self.setWindowTitle(getWindowTitle())
        geo = self._settings.getSetting("window_geometry", {})
        self.setGeometry(
            geo.get("x", 100),
            geo.get("y", 100),
            geo.get("width", 1400),
            geo.get("height", 800),
        )
        self.setMinimumSize(800, 500)

    # --------------------------------------------------------
    # Method: _initMenuBar
    # Purpose: Creates the menu bar with File, Edit, View,
    #          Bookmarks, and Help menus. Settings lives under Edit.
    # --------------------------------------------------------
    def _initMenuBar(self):
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        self._action_new_folder = QAction("New Folder\tF8", self)
        self._action_new_folder.setToolTip(
            "New folder\n\n"
            "Create a new folder in the active panel’s current directory. Shortcut: F8."
        )
        self._action_new_folder.triggered.connect(self._onNewFolder)
        file_menu.addAction(self._action_new_folder)

        file_menu.addSeparator()

        self._action_exit = QAction("Exit\tAlt+F4", self)
        self._action_exit.setToolTip("Exit\n\nClose the application. Shortcut: Alt+F4.")
        self._action_exit.triggered.connect(self.close)
        file_menu.addAction(self._action_exit)

        # --- Edit Menu ---
        edit_menu = menu_bar.addMenu("&Edit")

        self._action_cut = QAction("Cut\tCtrl+X", self)
        self._action_cut.setToolTip(
            "Cut\n\n"
            "Remove selected items and place them on the clipboard for moving. Shortcut: Ctrl+X."
        )
        self._action_cut.triggered.connect(self._onCut)
        edit_menu.addAction(self._action_cut)

        self._action_copy_clip = QAction("Copy\tCtrl+C", self)
        self._action_copy_clip.setToolTip(
            "Copy\n\nCopy selected items to the clipboard. Shortcut: Ctrl+C."
        )
        self._action_copy_clip.triggered.connect(self._onCopyToClipboard)
        edit_menu.addAction(self._action_copy_clip)

        self._action_paste = QAction("Paste\tCtrl+V", self)
        self._action_paste.setToolTip(
            "Paste\n\n"
            "Paste into the active panel’s folder: items copied in this app, or files/folders "
            "copied or cut in the system file manager (Explorer, Finder, …). Shortcut: Ctrl+V."
        )
        self._action_paste.triggered.connect(self._onPaste)
        edit_menu.addAction(self._action_paste)

        edit_menu.addSeparator()

        self._action_select_all = QAction("Select All\tCtrl+A", self)
        self._action_select_all.setToolTip(
            "Select all\n\nSelect every item in the active panel. Shortcut: Ctrl+A."
        )
        self._action_select_all.triggered.connect(self._onSelectAll)
        edit_menu.addAction(self._action_select_all)

        edit_menu.addSeparator()

        self._action_rename = QAction("Rename\tF2", self)
        self._action_rename.setToolTip(
            "Rename\n\nRename the selected item. Shortcut: F2."
        )
        self._action_rename.triggered.connect(self._onRename)
        edit_menu.addAction(self._action_rename)

        self._action_batch_rename = QAction("Batch Rename...\tCtrl+M", self)
        self._action_batch_rename.setToolTip(
            "Batch rename\n\n"
            "Rename multiple files using patterns and rules. Shortcut: Ctrl+M."
        )
        self._action_batch_rename.triggered.connect(self._onBatchRename)
        edit_menu.addAction(self._action_batch_rename)

        edit_menu.addSeparator()

        self._action_settings = QAction("Settings...", self)
        self._action_settings.setToolTip(
            "Settings\n\n"
            "Theme, font size, hidden files, delete confirmation, and default folder paths for new sessions."
        )
        self._action_settings.triggered.connect(self._onOpenSettings)
        edit_menu.addAction(self._action_settings)

        # --- View Menu ---
        view_menu = menu_bar.addMenu("&View")

        self._action_refresh = QAction("Refresh (both panels)", self)
        self._action_refresh.setToolTip(
            "Refresh both panels\n\nReload file listings in the left and right panels."
        )
        self._action_refresh.triggered.connect(self._onRefresh)
        view_menu.addAction(self._action_refresh)

        view_menu.addSeparator()

        self._action_show_hidden = QAction("Show Hidden Files", self)
        self._action_show_hidden.setToolTip(
            "Show hidden files\n\nToggle display of hidden and system items."
        )
        self._action_show_hidden.setCheckable(True)
        self._action_show_hidden.setChecked(
            self._settings.getSetting("show_hidden_files", False)
        )
        self._action_show_hidden.triggered.connect(self._onToggleHidden)
        view_menu.addAction(self._action_show_hidden)

        view_menu.addSeparator()
        self._action_swap_panes = QAction("Swap Pane Paths\tCtrl+Shift+S", self)
        self._action_swap_panes.setToolTip(
            "Swap pane paths\n\n"
            "Exchange the left and right folder paths. Shortcut: Ctrl+Shift+S."
        )
        self._action_swap_panes.triggered.connect(self._onSwapPanels)
        view_menu.addAction(self._action_swap_panes)

        view_menu.addSeparator()
        self._action_toggle_library_active = QAction("Toggle Library Browser (Active Panel)\tCtrl+Shift+L", self)
        self._action_toggle_library_active.setToolTip(
            "Library browser (active panel)\n\n"
            "Show or hide the library browser in the active panel’s slot. Shortcut: Ctrl+Shift+L."
        )
        self._action_toggle_library_active.triggered.connect(self._onToggleLibraryBrowserActive)
        view_menu.addAction(self._action_toggle_library_active)

        self._action_toggle_library_left = QAction("Toggle Library Browser (Left)", self)
        self._action_toggle_library_left.setToolTip(
            "Library browser (left)\n\nShow or hide the library browser in the left panel slot."
        )
        self._action_toggle_library_left.triggered.connect(lambda: self._toggleLibraryBrowser("left"))
        view_menu.addAction(self._action_toggle_library_left)

        self._action_toggle_library_right = QAction("Toggle Library Browser (Right)", self)
        self._action_toggle_library_right.setToolTip(
            "Library browser (right)\n\nShow or hide the library browser in the right panel slot."
        )
        self._action_toggle_library_right.triggered.connect(lambda: self._toggleLibraryBrowser("right"))
        view_menu.addAction(self._action_toggle_library_right)

        view_menu.addSeparator()
        self._action_mirror = QAction("Mirror\tCtrl+Shift+M", self)
        self._action_mirror.triggered.connect(self._onMirrorToOther)
        view_menu.addAction(self._action_mirror)

        # --- Bookmarks Menu ---
        self._bookmarks_menu = menu_bar.addMenu("&Bookmarks")
        self._rebuildBookmarksMenu()

        # --- Libraries Menu ---
        libraries_menu = menu_bar.addMenu("&Libraries")

        self._action_add_library_root = QAction("Add Current Folder To Library...", self)
        self._action_add_library_root.setToolTip(
            "Add current folder to library\n\n"
            "Register the active panel’s folder as a library root for tagging and search."
        )
        self._action_add_library_root.triggered.connect(self._onAddCurrentFolderToLibrary)
        libraries_menu.addAction(self._action_add_library_root)

        self._action_assign_current_folder_tags = QAction("Assign Tags To Current Folder...", self)
        self._action_assign_current_folder_tags.setToolTip(
            "Assign tags to current folder\n\n"
            "Edit tags for the folder shown in the active panel."
        )
        self._action_assign_current_folder_tags.triggered.connect(self._onAssignCurrentFolderTags)
        libraries_menu.addAction(self._action_assign_current_folder_tags)

        libraries_menu.addSeparator()

        self._action_scan_libraries = QAction("Scan Library Roots", self)
        self._action_scan_libraries.setToolTip(
            "Scan library roots\n\nRescan indexed folders under each library root."
        )
        self._action_scan_libraries.triggered.connect(self._onScanLibraries)
        libraries_menu.addAction(self._action_scan_libraries)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")
        self._action_about = QAction("About", self)
        self._action_about.setToolTip(
            "About\n\nShow the application name, version, and credits."
        )
        self._action_about.triggered.connect(self._onAbout)
        help_menu.addAction(self._action_about)

    # --------------------------------------------------------
    # Method: _initToolBar
    # Purpose: Creates the main toolbar with action buttons.
    # --------------------------------------------------------
    def _initToolBar(self):
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)
        style = QApplication.instance().style()

        self._tb_copy = QAction("\U0001F4CB Copy (F6)", self)
        self._tb_copy.setToolTip(
            "Copy to other panel\n\n"
            "Copy selected items to the opposite panel. Shortcut: F6."
        )
        self._tb_copy.triggered.connect(self._onCopyToOther)
        toolbar.addAction(self._tb_copy)

        self._tb_move = QAction("\U0001F4E6 Move (F7)", self)
        self._tb_move.setToolTip(
            "Move to other panel\n\n"
            "Move selected items to the opposite panel. Shortcut: F7."
        )
        self._tb_move.triggered.connect(self._onMoveToOther)
        toolbar.addAction(self._tb_move)

        self._tb_delete = QAction("\U0001F5D1 Delete (F9)", self)
        self._tb_delete.setToolTip(
            "Delete\n\nDelete selected items. Shortcut: F9."
        )
        self._tb_delete.triggered.connect(self._onDelete)
        toolbar.addAction(self._tb_delete)

        toolbar.addSeparator()

        self._tb_new_folder = QAction("\U0001F4C1 New Folder (F8)", self)
        self._tb_new_folder.setToolTip(
            "New folder\n\nCreate a folder in the active panel. Shortcut: F8."
        )
        self._tb_new_folder.triggered.connect(self._onNewFolder)
        toolbar.addAction(self._tb_new_folder)

        self._tb_rename = QAction("\u270F Rename (F2)", self)
        self._tb_rename.setToolTip(
            "Rename\n\nRename the selected item. Shortcut: F2."
        )
        self._tb_rename.triggered.connect(self._onRename)
        toolbar.addAction(self._tb_rename)

        self._tb_batch_rename = QAction("\U0001F504 Batch Rename", self)
        self._tb_batch_rename.setToolTip(
            "Batch rename\n\n"
            "Rename multiple files in the current folder. Shortcut: Ctrl+M."
        )
        self._tb_batch_rename.triggered.connect(self._onBatchRename)
        toolbar.addAction(self._tb_batch_rename)

        toolbar.addSeparator()

        self._tb_bookmark = QAction("\u2B50 Bookmark", self)
        self._tb_bookmark.setToolTip(
            "Bookmark folder\n\n"
            "Save the active panel’s path as a bookmark. Shortcut: Ctrl+Shift+B."
        )
        self._tb_bookmark.triggered.connect(self._onAddBookmark)
        toolbar.addAction(self._tb_bookmark)

        self._tb_open_explorer = QAction("Explorer", self)
        self._tb_open_explorer.setToolTip(
            "Open in Explorer\n\n"
            "Open the active panel’s folder in the system file manager."
        )
        self._tb_open_explorer.setIcon(style.standardIcon(QStyle.SP_DirOpenIcon))
        self._tb_open_explorer.triggered.connect(self._onOpenActivePathInExplorer)
        toolbar.addAction(self._tb_open_explorer)

        self._tb_refresh = QAction("\U0001F504 Refresh", self)
        self._tb_refresh.setToolTip(
            "Refresh both panels\n\n"
            "Reload both panels. F5 refreshes only the active panel."
        )
        self._tb_refresh.triggered.connect(self._onRefresh)
        toolbar.addAction(self._tb_refresh)

    # --------------------------------------------------------
    # Method: _initPanels
    # Purpose: Creates the layout: bookmarks pane | dual file panes
    #          with a center column of Copy/Move/Swap/Mirror buttons.
    #          Each panel slot is a QStackedWidget that can toggle
    #          between a FilePanel and a LibraryBrowserPanel.
    # --------------------------------------------------------
    def _initPanels(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 0)
        main_layout.setSpacing(0)

        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(0)

        self._left_panel = FilePanel("left", self, settings_manager=self._settings)
        self._right_panel = FilePanel("right", self, settings_manager=self._settings)

        self._left_library_browser = LibraryBrowserPanel("left", self)
        self._right_library_browser = LibraryBrowserPanel("right", self)
        self._connectLibraryBrowser(self._left_library_browser, "left")
        self._connectLibraryBrowser(self._right_library_browser, "right")

        self._left_stack = QStackedWidget()
        self._left_stack.addWidget(self._left_panel)
        self._left_stack.addWidget(self._left_library_browser)

        self._right_stack = QStackedWidget()
        self._right_stack.addWidget(self._right_panel)
        self._right_stack.addWidget(self._right_library_browser)

        self._center_buttons = self._buildCenterButtons()

        panels_layout.addWidget(self._left_stack, 1)
        panels_layout.addWidget(self._center_buttons)
        panels_layout.addWidget(self._right_stack, 1)

        file_panes_widget = QWidget()
        file_panes_widget.setLayout(panels_layout)

        self._bookmarks_panel = BookmarksPanel(self._settings, self)
        self._bookmarks_panel.bookmarkActivated.connect(self._onBookmarkPanelActivated)
        self._bookmarks_panel.structureChanged.connect(self._onBookmarksStructureChanged)
        self._bookmarks_panel.addCurrentFolderRequested.connect(self._onAddBookmark)

        self._libraries_panel = LibrariesPanel(self)
        self._libraries_panel.navigateRequested.connect(self._onLibraryNavigateRequested)
        self._libraries_panel.addLibraryRequested.connect(self._onAddCurrentFolderToLibrary)
        self._libraries_panel.scanLibrariesRequested.connect(self._onScanLibraries)

        self._sidebar_tabs = QTabWidget(self)
        self._sidebar_tabs.setObjectName("sidebarTabs")
        self._sidebar_tabs.addTab(self._bookmarks_panel, "Bookmarks")
        self._sidebar_tabs.addTab(self._libraries_panel, "Libraries")
        self._sidebar_tabs.setTabToolTip(
            0,
            "Bookmarks\n\nQuick access to saved folder and file shortcuts.",
        )
        self._sidebar_tabs.setTabToolTip(
            1,
            "Libraries\n\nTag-based library roots and matching folders.",
        )
        self._sidebar_tabs.setMinimumWidth(100)
        self._sidebar_tabs.setMaximumWidth(400)

        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.addWidget(self._sidebar_tabs)
        self._main_splitter.addWidget(file_panes_widget)
        bm_width = self._settings.getState("bookmarks_panel_width")
        if bm_width and isinstance(bm_width, (int, float)) and 100 <= bm_width <= 400:
            self._main_splitter.setSizes([int(bm_width), 1200])
        else:
            self._main_splitter.setSizes([200, 1200])

        main_layout.addWidget(self._main_splitter, 1)

        self.setCentralWidget(central)

        self._left_panel.activated.connect(lambda: self._setActivePanel(self._left_panel))
        self._right_panel.activated.connect(lambda: self._setActivePanel(self._right_panel))
        self._left_panel.tableView().clicked.connect(lambda: self._setActivePanel(self._left_panel))
        self._right_panel.tableView().clicked.connect(lambda: self._setActivePanel(self._right_panel))

        self._left_panel.fileDoubleClicked.connect(self._onFileOpen)
        self._right_panel.fileDoubleClicked.connect(self._onFileOpen)

        self._left_panel.filesDropped.connect(self._onDroppedFiles)
        self._right_panel.filesDropped.connect(self._onDroppedFiles)

        self._left_panel.pathCopied.connect(
            lambda p: self._showStatus(f"Copied path: {p}")
        )
        self._right_panel.pathCopied.connect(
            lambda p: self._showStatus(f"Copied path: {p}")
        )

        self._left_panel.folderCreated.connect(self._onFolderCreatedFromPanel)
        self._right_panel.folderCreated.connect(self._onFolderCreatedFromPanel)

        self._left_panel.selectionChanged.connect(self._updateStatusBar)
        self._right_panel.selectionChanged.connect(self._updateStatusBar)

        self._left_panel.tableView().setContextMenuPolicy(Qt.CustomContextMenu)
        self._left_panel.tableView().customContextMenuRequested.connect(
            lambda pos: self._showContextMenu(self._left_panel, pos)
        )
        self._right_panel.tableView().setContextMenuPolicy(Qt.CustomContextMenu)
        self._right_panel.tableView().customContextMenuRequested.connect(
            lambda pos: self._showContextMenu(self._right_panel, pos)
        )

        self._setActivePanel(self._left_panel)

    # --------------------------------------------------------
    # Method: _buildCenterButtons
    # Purpose: Creates the vertical column of directional
    #          copy/move buttons that sits between the panels.
    #          Arrows update dynamically based on active panel.
    # --------------------------------------------------------
    def _buildCenterButtons(self):
        frame = QFrame()
        frame.setObjectName("centerPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 8, 2, 8)
        layout.setSpacing(6)

        layout.addStretch(1)

        self._btn_copy_dir = QPushButton()
        self._btn_copy_dir.setToolTip(
            "Copy to other panel\n\n"
            "Copy selected items from the active panel to the opposite panel. Shortcut: F6."
        )
        self._btn_copy_dir.setFocusPolicy(Qt.NoFocus)
        self._btn_copy_dir.clicked.connect(self._onCopyToOther)
        layout.addWidget(self._btn_copy_dir)

        self._lbl_copy = QLabel("COPY")
        self._lbl_copy.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_copy)

        layout.addSpacing(12)

        self._btn_move_dir = QPushButton()
        self._btn_move_dir.setToolTip(
            "Move to other panel\n\n"
            "Move selected items from the active panel to the opposite panel. Shortcut: F7."
        )
        self._btn_move_dir.setFocusPolicy(Qt.NoFocus)
        self._btn_move_dir.clicked.connect(self._onMoveToOther)
        layout.addWidget(self._btn_move_dir)

        self._lbl_move = QLabel("MOVE")
        self._lbl_move.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_move)

        layout.addSpacing(16)

        self._btn_swap = QPushButton("\u21C4")
        self._btn_swap.setToolTip(
            "Swap panes\n\n"
            "Exchange the left and right folder paths. Shortcut: Ctrl+Shift+S."
        )
        self._btn_swap.setFocusPolicy(Qt.NoFocus)
        self._btn_swap.clicked.connect(self._onSwapPanels)
        layout.addWidget(self._btn_swap)

        self._lbl_swap = QLabel("SWAP")
        self._lbl_swap.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_swap)

        layout.addSpacing(16)

        self._btn_mirror = QPushButton("\u229C")
        self._btn_mirror.setFocusPolicy(Qt.NoFocus)
        self._btn_mirror.clicked.connect(self._onMirrorToOther)
        layout.addWidget(self._btn_mirror)

        self._lbl_mirror = QLabel("MIRROR")
        self._lbl_mirror.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_mirror)

        layout.addStretch(1)

        self._updateDirectionButtons()
        return frame

    # --------------------------------------------------------
    # Method: _updateDirectionButtons
    # Purpose: Updates arrow direction on center buttons based
    #          on which panel is currently active.
    # --------------------------------------------------------
    def _updateDirectionButtons(self):
        if self._active_panel == self._left_panel:
            self._btn_copy_dir.setText("\u27A1")
            self._btn_move_dir.setText("\u27A1")
            self._btn_copy_dir.setToolTip(
                "Copy to other panel\n\n"
                "Copy selected items to the right panel. Flow: Left \u2192 Right. Shortcut: F6."
            )
            self._btn_move_dir.setToolTip(
                "Move to other panel\n\n"
                "Move selected items to the right panel. Flow: Left \u2192 Right. Shortcut: F7."
            )
        else:
            self._btn_copy_dir.setText("\u2B05")
            self._btn_move_dir.setText("\u2B05")
            self._btn_copy_dir.setToolTip(
                "Copy to other panel\n\n"
                "Copy selected items to the left panel. Flow: Right \u2192 Left. Shortcut: F6."
            )
            self._btn_move_dir.setToolTip(
                "Move to other panel\n\n"
                "Move selected items to the left panel. Flow: Right \u2192 Left. Shortcut: F7."
            )

    # --------------------------------------------------------
    # Method: _initBottomBar
    # Purpose: Creates the Total Commander-style bottom button
    #          bar with F-key shortcuts.
    # --------------------------------------------------------
    def _initBottomBar(self):
        bottom_frame = QFrame()
        bottom_frame.setObjectName("bottomBar")
        bottom_frame.setFixedHeight(38)

        layout = QHBoxLayout(bottom_frame)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        button_defs = [
            (
                "F2 Rename",
                self._onRename,
                "Rename\n\nRename the selected item in the active panel. Shortcut: F2.",
            ),
            (
                "F5 Refresh",
                self._onRefreshActivePanel,
                "Refresh\n\nReload the listing for the active panel only. Shortcut: F5.",
            ),
            (
                "F6 Copy",
                self._onCopyToOther,
                "Copy\n\nCopy selected items to the opposite panel. Shortcut: F6.",
            ),
            (
                "F7 Move",
                self._onMoveToOther,
                "Move\n\nMove selected items to the opposite panel. Shortcut: F7.",
            ),
            (
                "F8 NewFolder",
                self._onNewFolder,
                "New folder\n\nCreate a folder in the active panel. Shortcut: F8.",
            ),
            (
                "F9 Delete",
                self._onDelete,
                "Delete\n\nDelete selected items. Shortcut: F9.",
            ),
        ]

        for text, callback, tip in button_defs:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.clicked.connect(callback)
            btn.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(btn, 1)

        self.centralWidget().layout().addWidget(bottom_frame)

    # --------------------------------------------------------
    # Method: _initStatusBar
    # --------------------------------------------------------
    def _initStatusBar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_info = QLabel("Ready")
        self._status_info.setObjectName("statusLabel")
        self._status_bar.addWidget(self._status_info, 1)

    # --------------------------------------------------------
    # Method: _initShortcuts
    # Purpose: Registers all keyboard shortcuts.
    # --------------------------------------------------------
    def _initShortcuts(self):
        shortcuts = {
            QKeySequence(Qt.Key_F2):                     self._onRename,
            QKeySequence(Qt.Key_F5):                     self._onRefreshActivePanel,
            QKeySequence(Qt.Key_F6):                     self._onCopyToOther,
            QKeySequence(Qt.Key_F7):                     self._onMoveToOther,
            QKeySequence(Qt.Key_F8):                     self._onNewFolder,
            QKeySequence(Qt.Key_F9):                     self._onDelete,
            QKeySequence(Qt.Key_Delete):                  self._onDelete,
            QKeySequence(Qt.Key_Return):                  self._onEnterPressed,
            QKeySequence(Qt.Key_Backspace):               self._onBackspace,
            QKeySequence("Ctrl+L"):                       self._onFocusAddressBar,
            QKeySequence(Qt.Key_Tab):                     self._onSwitchPanel,
            QKeySequence("Ctrl+A"):                       self._onSelectAll,
            QKeySequence("Ctrl+Shift+B"):                 self._onAddBookmark,
            QKeySequence("Ctrl+X"):                       self._onCut,
            QKeySequence("Ctrl+C"):                       self._onCopyToClipboard,
            QKeySequence("Ctrl+V"):                       self._onPaste,
            QKeySequence("Ctrl+M"):                       self._onBatchRename,
            QKeySequence("Ctrl+Shift+S"):                 self._onSwapPanels,
            QKeySequence("Ctrl+Shift+L"):                 self._onToggleLibraryBrowserActive,
            QKeySequence("Ctrl+Shift+M"):                 self._onMirrorToOther,
        }

        for key_seq, callback in shortcuts.items():
            action = QAction(self)
            action.setShortcut(key_seq)
            action.setShortcutContext(Qt.WindowShortcut)
            action.triggered.connect(callback)
            self.addAction(action)

    # --------------------------------------------------------
    # Method: _restoreState
    # Purpose: Loads saved panel paths from state.json and
    #          navigates both panels to their last location.
    # --------------------------------------------------------
    def _restoreState(self):
        home = os.path.expanduser("~")

        left_state = self._settings.getPanelState("left")
        right_state = self._settings.getPanelState("right")

        left_path = left_state.get("current_path", "") or self._settings.getSetting("default_left_path", "") or home
        right_path = right_state.get("current_path", "") or self._settings.getSetting("default_right_path", "") or home

        if not os.path.isdir(left_path):
            left_path = home
        if not os.path.isdir(right_path):
            right_path = home

        self._left_panel.restoreHistoryData(left_state)
        self._right_panel.restoreHistoryData(right_state)

        if not self._left_panel.currentPath():
            self._left_panel.navigateTo(left_path)
        if not self._right_panel.currentPath():
            self._right_panel.navigateTo(right_path)

        fallback_widths = self._settings.getSetting("column_widths", {})
        if fallback_widths and not left_state.get("column_widths"):
            self._left_panel.applyColumnWidths(fallback_widths)
        if fallback_widths and not right_state.get("column_widths"):
            self._right_panel.applyColumnWidths(fallback_widths)

        show_hidden = self._settings.getSetting("show_hidden_files", False)
        self._left_panel.setShowHidden(show_hidden)
        self._right_panel.setShowHidden(show_hidden)

        sidebar_state = self._settings.getSidebarState()
        current_tab = sidebar_state.get("current_tab", "bookmarks")
        if current_tab == "libraries":
            self._sidebar_tabs.setCurrentIndex(1)
        else:
            self._sidebar_tabs.setCurrentIndex(0)

        self._library_manager.refreshLibraries()
        self._reloadLibrariesPanel()

    # --------------------------------------------------------
    # Active Panel Management
    # --------------------------------------------------------
    def _setActivePanel(self, panel):
        if self._active_panel == panel:
            return
        if self._active_panel:
            self._active_panel.setActive(False)
        self._active_panel = panel
        panel.setActive(True)
        self._updateStatusBar()
        if hasattr(self, "_btn_copy_dir"):
            self._updateDirectionButtons()

    def _getInactivePanel(self):
        if self._active_panel == self._left_panel:
            return self._right_panel
        return self._left_panel

    # --------------------------------------------------------
    # Swap pane paths: left <-> right
    # --------------------------------------------------------
    def _onSwapPanels(self):
        left_path = self._left_panel.currentPath()
        right_path = self._right_panel.currentPath()
        if not left_path or not right_path:
            return
        self._left_panel.navigateTo(right_path)
        self._right_panel.navigateTo(left_path)
        self._showStatus("Panes swapped.")

    # --------------------------------------------------------
    # File Operation Handlers
    # --------------------------------------------------------
    def _onCopyToOther(self):
        if not self._active_panel:
            return
        paths = self._active_panel.selectedPaths()
        if not paths:
            self._showStatus("No files selected.")
            return
        dest = self._getInactivePanel().currentPath()
        if not dest:
            self._showStatus("No destination panel.")
            return

        success, msg = copyFiles(paths, dest, self)
        self._refreshBothPanels()
        self._showStatus(msg)

    def _onMoveToOther(self):
        if not self._active_panel:
            return
        paths = self._active_panel.selectedPaths()
        if not paths:
            self._showStatus("No files selected.")
            return
        dest = self._getInactivePanel().currentPath()
        if not dest:
            self._showStatus("No destination panel.")
            return

        success, msg = moveFiles(paths, dest, self)
        self._refreshBothPanels()
        self._showStatus(msg)

    def _onDelete(self):
        if not self._active_panel or self._active_panel.isRenaming():
            return
        paths = self._active_panel.selectedPaths()
        if not paths:
            self._showStatus("No files selected.")
            return

        confirm = self._settings.getSetting("confirm_delete", True)
        success, msg = deleteFiles(paths, self, confirm=confirm)
        self._refreshBothPanels()
        self._showStatus(msg)

    def _onRename(self):
        if not self._active_panel:
            return
        if self._active_panel.isRenaming():
            return
        self._active_panel.startRename()

    def _onFolderCreatedFromPanel(self, folder_name):
        self._showStatus(f"Created folder: {folder_name}")

    def _onNewFolder(self):
        if not self._active_panel:
            return
        self._active_panel.createNewFolder()

    # --------------------------------------------------------
    # Batch Rename: Opens the multi-rename dialog.
    # If files are selected, operates on selection only.
    # Otherwise operates on all files in the current folder.
    # --------------------------------------------------------
    def _onBatchRename(self):
        if not self._active_panel:
            return
        current_dir = self._active_panel.currentPath()
        if not current_dir:
            return

        model = self._active_panel.sourceModel()
        entries = [
            model.entryAt(i) for i in range(model.rowCount())
            if model.entryAt(i) is not None
        ]

        if not entries:
            self._showStatus("No files to rename.")
            return

        dialog = BatchRenameDialog(entries, current_dir, self)
        if dialog.exec_() == QDialog.Accepted:
            self._refreshBothPanels()
            self._showStatus(f"Batch rename complete.")

    # --------------------------------------------------------
    # F5: Refresh active panel only (Explorer-style)
    # --------------------------------------------------------
    def _onRefreshActivePanel(self):
        if not self._active_panel:
            return
        self._active_panel.refresh()
        self._showStatus("Refreshed.")

    # --------------------------------------------------------
    # Enter Key: If renaming, commit the rename. Otherwise
    # open the file or navigate into the folder.
    # --------------------------------------------------------
    def _onEnterPressed(self):
        if not self._active_panel:
            return
        if self._active_panel.isRenaming():
            self._active_panel.commitRename()
            return
        entries = self._active_panel.selectedEntries()
        if len(entries) == 1:
            entry = entries[0]
            if entry["is_dir"]:
                self._active_panel.navigateTo(entry["full_path"])
            else:
                self._onFileOpen(entry)

    # --------------------------------------------------------
    # Open file with system default application
    # --------------------------------------------------------
    def _onFileOpen(self, entry):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(entry["full_path"]))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file:\n{e}")

    # --------------------------------------------------------
    # Navigation
    # --------------------------------------------------------
    def _onBackspace(self):
        if not self._active_panel or self._active_panel.isRenaming():
            return
        self._active_panel.goUp()

    def _onFocusAddressBar(self):
        if self._active_panel:
            self._active_panel.pathEdit().setFocus()
            self._active_panel.pathEdit().selectAll()

    def _onSwitchPanel(self):
        if self._active_panel == self._left_panel:
            self._setActivePanel(self._right_panel)
            self._right_panel.tableView().setFocus()
        else:
            self._setActivePanel(self._left_panel)
            self._left_panel.tableView().setFocus()

    # --------------------------------------------------------
    # Clipboard Operations
    # --------------------------------------------------------
    def _onCut(self):
        if not self._active_panel:
            return
        self._clipboard_paths = self._active_panel.selectedPaths()
        self._clipboard_mode = "cut"
        if self._clipboard_paths:
            self._syncNativeFileClipboard()
            self._showStatus(f"Cut {len(self._clipboard_paths)} item(s)")

    def _onCopyToClipboard(self):
        if not self._active_panel:
            return
        self._clipboard_paths = self._active_panel.selectedPaths()
        self._clipboard_mode = "copy"
        if self._clipboard_paths:
            self._syncNativeFileClipboard()
            self._showStatus(f"Copied {len(self._clipboard_paths)} item(s) to clipboard")

    def _pathsFromOsClipboard(self):
        """
        Return (paths, mode) from the OS file clipboard (local file URLs).
        mode is 'copy' or 'cut' (Windows Explorer cut sets move → 'cut').
        Returns ([], None) if the clipboard has no usable file paths.
        """
        md = QApplication.clipboard().mimeData()
        if not md or not md.hasUrls():
            return [], None
        paths = []
        for u in md.urls():
            if u.isLocalFile():
                p = os.path.normpath(u.toLocalFile())
                if p and os.path.exists(p):
                    paths.append(p)
        if not paths:
            return [], None
        seen = set()
        uniq = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                uniq.append(p)
        paths = uniq

        mode = "copy"
        eff = getClipboardDropEffect()
        if eff == "move":
            mode = "cut"
        return paths, mode

    def _hasPasteSource(self):
        if self._clipboard_paths:
            return True
        paths, _ = self._pathsFromOsClipboard()
        return bool(paths)

    def _onPaste(self):
        if not self._active_panel:
            return

        dest = self._active_panel.currentPath()
        if not dest:
            return

        os_paths, os_mode = self._pathsFromOsClipboard()
        if os_paths:
            self._clipboard_paths = []
            self._clipboard_mode = None
            if os_mode == "cut":
                success, msg = moveFiles(os_paths, dest, self)
            else:
                success, msg = copyFiles(os_paths, dest, self)
            self._refreshBothPanels()
            self._showStatus(msg)
            return

        if not self._clipboard_paths:
            self._showStatus("Nothing to paste.")
            return

        if self._clipboard_mode == "copy":
            success, msg = copyFiles(self._clipboard_paths, dest, self)
        elif self._clipboard_mode == "cut":
            success, msg = moveFiles(self._clipboard_paths, dest, self)
            if success:
                self._clipboard_paths = []
                self._clipboard_mode = None
        else:
            return

        self._refreshBothPanels()
        self._showStatus(msg)

    # --------------------------------------------------------
    # Method: _syncNativeFileClipboard
    # Purpose: Mirrors the app clipboard to the Windows shell
    #          clipboard so files can be pasted into Explorer.
    # --------------------------------------------------------
    def _syncNativeFileClipboard(self):
        if not self._clipboard_paths or self._clipboard_mode not in ("copy", "cut"):
            return False
        return setFileClipboard(self._clipboard_paths, self._clipboard_mode)

    # --------------------------------------------------------
    # Select All
    # --------------------------------------------------------
    def _onSelectAll(self):
        if self._active_panel:
            self._active_panel.tableView().selectAll()

    # --------------------------------------------------------
    # View
    # --------------------------------------------------------
    def _onRefresh(self):
        self._left_panel.refresh()
        self._right_panel.refresh()
        self._showStatus("Refreshed.")

    def _onToggleHidden(self, checked):
        self._settings.setSetting("show_hidden_files", checked)
        self._left_panel.setShowHidden(checked)
        self._right_panel.setShowHidden(checked)

    def _onOpenSettings(self):
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        for key, value in values.items():
            self._settings.setSetting(key, value)

        self._action_show_hidden.setChecked(values["show_hidden_files"])
        self._left_panel.setShowHidden(values["show_hidden_files"])
        self._right_panel.setShowHidden(values["show_hidden_files"])

        app = QApplication.instance()
        applyTheme(app, values["theme_mode"], int(values["font_size"]))

        self._settings.saveSettings()
        self._updateMirrorTooltips()
        self._showStatus("Settings saved.")

    # --------------------------------------------------------
    # Bookmarks
    # --------------------------------------------------------
    def _onAddBookmark(self):
        if not self._active_panel:
            return
        path = self._active_panel.currentPath()
        if not path:
            return

        default_name = os.path.basename(path) or path
        name, ok = QInputDialog.getText(
            self, "Add Bookmark", "Bookmark name:", text=default_name
        )
        if ok and name.strip():
            self._settings.addBookmark(name.strip(), path)
            self._bookmarks_panel.loadStructure()
            self._rebuildBookmarksMenu()
            self._showStatus(f"Bookmarked: {name.strip()}")

    def _onAddFileBookmark(self, entry):
        """Add the selected file as a bookmark (double-click in bookmarks pane will run it)."""
        path = entry.get("full_path")
        if not path or not os.path.isfile(path):
            return
        default_name = entry.get("name", os.path.basename(path))
        name, ok = QInputDialog.getText(
            self, "Add File Bookmark", "Bookmark name:", text=default_name
        )
        if ok and name.strip():
            self._settings.addBookmark(name.strip(), path)
            self._bookmarks_panel.loadStructure()
            self._rebuildBookmarksMenu()
            self._showStatus(f"Bookmarked: {name.strip()}")

    def _rebuildBookmarksMenu(self):
        self._bookmarks_menu.clear()

        add_action = QAction("Add Current Folder...", self)
        add_action.setToolTip(
            "Add bookmark\n\n"
            "Save the active panel’s current folder as a named bookmark."
        )
        add_action.triggered.connect(self._onAddBookmark)
        self._bookmarks_menu.addAction(add_action)

        self._bookmarks_menu.addSeparator()

        bookmarks = self._settings.getBookmarks()
        if not bookmarks:
            empty_action = QAction("(no bookmarks)", self)
            empty_action.setToolTip(
                "No bookmarks\n\nUse “Add Current Folder…” to create your first bookmark."
            )
            empty_action.setEnabled(False)
            self._bookmarks_menu.addAction(empty_action)
        else:
            for bm in bookmarks:
                bm_name = bm.get("name", "")
                bm_path = bm.get("path", "")
                action = QAction(f"{bm_name}  \u2192  {bm_path}", self)
                action.setToolTip(
                    "Go to bookmark\n\n"
                    f"Open this path: {bm_path}"
                )
                action.setData(bm_path)
                action.triggered.connect(self._onBookmarkClicked)
                self._bookmarks_menu.addAction(action)

            self._bookmarks_menu.addSeparator()
            manage_action = QAction("Remove a Bookmark...", self)
            manage_action.setToolTip(
                "Remove bookmark\n\nChoose a bookmark to delete from the list."
            )
            manage_action.triggered.connect(self._onRemoveBookmark)
            self._bookmarks_menu.addAction(manage_action)

    def _onBookmarkClicked(self):
        action = self.sender()
        if not action:
            return
        path = action.data()
        if not path:
            return
        if os.path.isfile(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        elif os.path.isdir(path) and self._active_panel:
            self._active_panel.navigateTo(path)

    def _onBookmarkPanelActivated(self, path):
        """Navigate the active pane to the clicked bookmark path."""
        if self._active_panel and path and os.path.isdir(path):
            self._active_panel.navigateTo(path)

    def _onBookmarksStructureChanged(self, structure):
        """Persist bookmarks structure when user reorders or edits in the panel."""
        self._settings.setBookmarksStructure(structure)
        self._rebuildBookmarksMenu()

    def _onRemoveBookmark(self):
        bookmarks = self._settings.getBookmarks()
        if not bookmarks:
            return

        names = [f"{bm['name']} -> {bm['path']}" for bm in bookmarks]
        from PyQt5.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(
            self, "Remove Bookmark", "Select bookmark to remove:", names, 0, False
        )
        if ok and item:
            idx = names.index(item)
            self._settings.removeBookmark(bookmarks[idx]["path"])
            self._bookmarks_panel.loadStructure()
            self._rebuildBookmarksMenu()
            self._showStatus("Bookmark removed.")

    # --------------------------------------------------------
    # Libraries / Tags
    # --------------------------------------------------------
    def _reloadLibrariesPanel(self, selected_library_id=""):
        if not selected_library_id and hasattr(self, "_libraries_panel"):
            selected_library_id = self._libraries_panel.selectedLibraryId()
        libraries = self._library_manager.getLibraries()
        tagged_folders = self._library_manager.getTaggedFolders()
        self._libraries_panel.setData(libraries, tagged_folders, selected_library_id)

        if hasattr(self, "_left_library_browser"):
            self._left_library_browser.setData(
                libraries, tagged_folders, self._left_library_browser.selectedLibraryId()
            )
        if hasattr(self, "_right_library_browser"):
            self._right_library_browser.setData(
                libraries, tagged_folders, self._right_library_browser.selectedLibraryId()
            )

    def _onScanLibraries(self):
        self._library_manager.refreshLibraries()
        self._reloadLibrariesPanel()
        self._showStatus("Library roots scanned.")

    def _onLibraryNavigateRequested(self, path):
        if not path or not os.path.isdir(path):
            self._showStatus("Selected library folder is offline or missing.")
            return
        if self._active_panel is None:
            self._setActivePanel(self._left_panel)
        self._active_panel.navigateTo(path)
        self._showStatus(f"Opened library folder: {path}")

    def _activeFolderCandidate(self):
        if not self._active_panel:
            return ""
        entries = self._active_panel.selectedEntries()
        if len(entries) == 1 and entries[0]["is_dir"]:
            return entries[0]["full_path"]
        current = self._active_panel.currentPath()
        return current if current and os.path.isdir(current) else ""

    def _promptLibraryRegistration(self, initial_root_path, initial_library_name=""):
        existing_names = [lib.get("name", "") for lib in self._library_manager.getLibraries()]
        dialog = LibraryRootDialog(
            existing_names,
            initial_root_path=initial_root_path,
            initial_library_name=initial_library_name,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return None

        values = dialog.values()
        library_name = values.get("library_name", "").strip()
        root_path = values.get("root_path", "").strip()
        if not library_name:
            QMessageBox.warning(self, "Library", "Library name is required.")
            return None
        if not root_path or not os.path.isdir(root_path):
            QMessageBox.warning(self, "Library", "Choose a valid root folder.")
            return None

        result = self._library_manager.registerLibraryRoot(
            library_name,
            root_path,
            root_name=values.get("root_name", "").strip(),
        )
        if result is None:
            QMessageBox.warning(self, "Library", "Could not register the selected library root.")
        return result

    def _onAddCurrentFolderToLibrary(self):
        folder_path = self._activeFolderCandidate()
        if not folder_path:
            QMessageBox.information(self, "Library", "Select a folder or open one in the active panel first.")
            return
        self._onAddFolderToLibrary(folder_path)

    def _onAddFolderToLibrary(self, folder_path):
        result = self._promptLibraryRegistration(folder_path)
        if result is None:
            return None
        self._reloadLibrariesPanel(result["library"]["id"])
        self._showStatus(
            f"Added root to library: {result['library'].get('name', 'Library')} -> {result['root'].get('path', '')}"
        )
        return result

    def _ensureLibraryContext(self, folder_path):
        context = self._library_manager.resolveFolderContext(folder_path)
        if context is not None:
            return context

        answer = QMessageBox.question(
            self,
            "Library required",
            "This folder is not under a known library root yet.\n\nAdd a library root now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return None

        result = self._promptLibraryRegistration(folder_path)
        if result is None:
            return None

        self._reloadLibrariesPanel(result["library"]["id"])
        return self._library_manager.resolveFolderContext(folder_path)

    def _onAssignCurrentFolderTags(self):
        folder_path = self._activeFolderCandidate()
        if not folder_path:
            QMessageBox.information(self, "Tags", "Select a folder or open one in the active panel first.")
            return
        self._onAssignFolderTags(folder_path)

    def _onAssignFolderTags(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Tags", "Choose a valid folder first.")
            return

        context = self._ensureLibraryContext(folder_path)
        if context is None:
            return

        record = self._library_manager.getFolderRecordForPath(folder_path) or {}
        known_tags = self._library_manager.getAvailableTags()
        dialog = TagAssignmentDialog(
            folder_path,
            existing_tags=record.get("tags", []),
            existing_note=record.get("note", ""),
            known_tags=known_tags,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.values()
        self._library_manager.assignTagsToFolder(folder_path, values.get("tags", []), values.get("note", ""))
        self._reloadLibrariesPanel(context["library"]["id"])
        self._showStatus(f"Tags updated for: {folder_path}")

    # --------------------------------------------------------
    # Library Browser Panel (full panel view)
    # --------------------------------------------------------
    def _connectLibraryBrowser(self, browser, side):
        browser.navigateRequested.connect(
            lambda path: self._onBrowserNavigateRequested(path, side)
        )
        browser.navigateInPanelRequested.connect(self._onBrowserNavigateInPanel)
        browser.switchToFilePanelRequested.connect(
            lambda: self._toggleLibraryBrowser(side)
        )
        browser.addLibraryRequested.connect(self._onAddCurrentFolderToLibrary)
        browser.scanLibrariesRequested.connect(self._onScanLibraries)
        browser.assignTagsRequested.connect(self._onAssignCurrentFolderTags)

    def _onBrowserNavigateRequested(self, path, browser_side):
        if not path or not os.path.isdir(path):
            self._showStatus("Selected folder is offline or missing.")
            return
        stack = self._left_stack if browser_side == "left" else self._right_stack
        panel = self._left_panel if browser_side == "left" else self._right_panel
        stack.setCurrentWidget(panel)
        panel.navigateTo(path)
        self._setActivePanel(panel)
        self._showStatus(f"Opened library folder: {path}")

    def _onBrowserNavigateInPanel(self, path, panel_side):
        if not path or not os.path.isdir(path):
            self._showStatus("Selected folder is offline or missing.")
            return
        panel = self._left_panel if panel_side == "left" else self._right_panel
        stack = self._left_stack if panel_side == "left" else self._right_stack
        stack.setCurrentWidget(panel)
        panel.navigateTo(path)
        self._showStatus(f"Opened library folder: {path}")

    def _onToggleLibraryBrowserActive(self):
        if self._active_panel == self._left_panel:
            self._toggleLibraryBrowser("left")
        else:
            self._toggleLibraryBrowser("right")

    def _toggleLibraryBrowser(self, side):
        stack = self._left_stack if side == "left" else self._right_stack
        browser = self._left_library_browser if side == "left" else self._right_library_browser

        if stack.currentWidget() == browser:
            file_panel = self._left_panel if side == "left" else self._right_panel
            stack.setCurrentWidget(file_panel)
            self._showStatus("Switched to file panel.")
        else:
            self._reloadLibraryBrowser(side)
            stack.setCurrentWidget(browser)
            self._showStatus("Switched to library browser.")

    def _reloadLibraryBrowser(self, side):
        browser = self._left_library_browser if side == "left" else self._right_library_browser
        libraries = self._library_manager.getLibraries()
        tagged_folders = self._library_manager.getTaggedFolders()
        selected_id = browser.selectedLibraryId()
        browser.setData(libraries, tagged_folders, selected_id)

    # --------------------------------------------------------
    # Mirror: Sync folder between panels (direction from Settings)
    # --------------------------------------------------------
    def _updateMirrorTooltips(self):
        tip = self._mirrorToolTipText()
        self._action_mirror.setToolTip(tip)
        if hasattr(self, "_btn_mirror"):
            self._btn_mirror.setToolTip(tip)

    def _mirrorToolTipText(self):
        mode = self._settings.getSetting("mirror_mode", "to_other")
        if mode == "to_active":
            body = (
                "Navigate the active panel to the inactive panel’s folder "
                "(Edit → Settings → Mirror: active follows inactive)."
            )
        else:
            body = (
                "Navigate the inactive panel to the active panel’s folder "
                "(Edit → Settings → Mirror: inactive follows active)."
            )
        return f"Mirror\n\n{body}\nShortcut: Ctrl+Shift+M."

    def _onMirrorToOther(self):
        if not self._active_panel:
            return
        mode = self._settings.getSetting("mirror_mode", "to_other")
        inactive = self._getInactivePanel()
        active = self._active_panel
        if mode == "to_active":
            source, target = inactive, active
            err = "Inactive panel has no folder to mirror."
            ok_msg = "Mirrored to active panel: {path}"
        else:
            source, target = active, inactive
            err = "Active panel has no folder to mirror."
            ok_msg = "Mirrored to other panel: {path}"
        path = source.currentPath()
        if not path or not os.path.isdir(path):
            self._showStatus(err)
            return
        target.navigateTo(path)
        self._showStatus(ok_msg.format(path=path))

    # --------------------------------------------------------
    # Right-Click Context Menu
    # --------------------------------------------------------
    def _showContextMenu(self, panel, pos):
        self._setActivePanel(panel)
        table = panel.tableView()
        index = table.indexAt(pos)

        menu = QMenu(self)

        entries = panel.selectedEntries()
        has_selection = len(entries) > 0
        single_selection = len(entries) == 1

        if single_selection:
            entry = entries[0]
            open_action = menu.addAction("Open")
            open_action.setToolTip(
                "Open\n\n"
                "Open the folder in this panel or launch the file with its default app."
            )
            open_action.triggered.connect(lambda: self._onContextOpen(entry))

            if not entry["is_dir"]:
                open_with_action = menu.addAction("Open With...")
                open_with_action.setToolTip(
                    "Open with\n\n"
                    "Choose another application to open this file (Windows “Open with” dialog)."
                )
                open_with_action.triggered.connect(lambda: self._onOpenWith(entry))

            menu.addSeparator()

        if has_selection:
            cut_action = menu.addAction("Cut\tCtrl+X")
            cut_action.setToolTip(
                "Cut\n\n"
                "Remove selected items and place them on the clipboard. Shortcut: Ctrl+X."
            )
            cut_action.triggered.connect(self._onCut)

            copy_action = menu.addAction("Copy\tCtrl+C")
            copy_action.setToolTip(
                "Copy\n\nCopy selected items to the clipboard. Shortcut: Ctrl+C."
            )
            copy_action.triggered.connect(self._onCopyToClipboard)

        paste_action = menu.addAction("Paste\tCtrl+V")
        paste_action.setToolTip(
            "Paste\n\n"
            "Paste items from this app’s clipboard, or files/folders copied or cut in "
            "Explorer / Finder. Shortcut: Ctrl+V."
        )
        paste_action.triggered.connect(self._onPaste)
        paste_action.setEnabled(self._hasPasteSource())

        menu.addSeparator()

        if has_selection:
            copy_other_action = menu.addAction("Copy to Other Panel\tF6")
            copy_other_action.setToolTip(
                "Copy to other panel\n\nCopy selected items to the opposite panel. Shortcut: F6."
            )
            copy_other_action.triggered.connect(self._onCopyToOther)

            move_other_action = menu.addAction("Move to Other Panel\tF7")
            move_other_action.setToolTip(
                "Move to other panel\n\nMove selected items to the opposite panel. Shortcut: F7."
            )
            move_other_action.triggered.connect(self._onMoveToOther)

            menu.addSeparator()

        if single_selection:
            rename_action = menu.addAction("Rename\tF2")
            rename_action.setToolTip(
                "Rename\n\nRename the selected item. Shortcut: F2."
            )
            rename_action.triggered.connect(self._onRename)

        if has_selection:
            delete_action = menu.addAction("Delete\tF9")
            delete_action.setToolTip(
                "Delete\n\nDelete selected items. Shortcut: F9."
            )
            delete_action.triggered.connect(self._onDelete)

        menu.addSeparator()

        new_folder_action = menu.addAction("New Folder\tF8")
        new_folder_action.setToolTip(
            "New folder\n\nCreate a folder in the current directory. Shortcut: F8."
        )
        new_folder_action.triggered.connect(self._onNewFolder)

        batch_rename_action = menu.addAction("Batch Rename...\tCtrl+M")
        batch_rename_action.setToolTip(
            "Batch rename\n\nRename multiple files using patterns. Shortcut: Ctrl+M."
        )
        batch_rename_action.triggered.connect(self._onBatchRename)

        menu.addSeparator()

        if single_selection:
            copy_path_action = menu.addAction("Copy Path to Clipboard")
            copy_path_action.setToolTip(
                "Copy path\n\nCopy the full path of this item as text."
            )
            copy_path_action.triggered.connect(
                lambda: self._copyPathToClipboard(entries[0]["full_path"])
            )

        if single_selection and entries[0]["is_dir"]:
            add_to_library_action = menu.addAction("Add To Library...")
            add_to_library_action.setToolTip(
                "Add to library\n\nRegister this folder as a library root."
            )
            add_to_library_action.triggered.connect(
                lambda: self._onAddFolderToLibrary(entries[0]["full_path"])
            )

            assign_tags_action = menu.addAction("Assign Tags...")
            assign_tags_action.setToolTip(
                "Assign tags\n\nEdit tags for this folder in the library system."
            )
            assign_tags_action.triggered.connect(
                lambda: self._onAssignFolderTags(entries[0]["full_path"])
            )

        bookmark_action = menu.addAction("Bookmark This Folder")
        bookmark_action.setToolTip(
            "Bookmark folder\n\nSave the current folder as a bookmark."
        )
        bookmark_action.triggered.connect(self._onAddBookmark)

        if single_selection and not entries[0]["is_dir"]:
            bookmark_file_action = menu.addAction("Bookmark This File")
            bookmark_file_action.setToolTip(
                "Bookmark file\n\nSave this file path as a bookmark (double-click opens it)."
            )
            bookmark_file_action.triggered.connect(
                lambda: self._onAddFileBookmark(entries[0])
            )

        if single_selection:
            menu.addSeparator()
            props_action = menu.addAction("Properties")
            props_action.setToolTip(
                "Properties\n\n"
                "Open a tabbed dialog: General (location, size, dates), Details (MIME, permissions), "
                "and checksums for files."
            )
            props_action.triggered.connect(lambda: self._showProperties(entries[0]))

        menu.exec_(table.viewport().mapToGlobal(pos))

    def _onContextOpen(self, entry):
        if entry["is_dir"]:
            self._active_panel.navigateTo(entry["full_path"])
        else:
            self._onFileOpen(entry)

    def _onOpenWith(self, entry):
        if platform.system() == "Windows":
            try:
                subprocess.Popen(["rundll32", "shell32.dll,OpenAs_RunDLL", entry["full_path"]])
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _copyPathToClipboard(self, path):
        clipboard = QApplication.clipboard()
        clipboard.setText(path)
        self._showStatus(f"Copied path: {path}")

    # --------------------------------------------------------
    # Method: _onOpenActivePathInExplorer
    # Purpose: Opens the active panel path in the system file
    #          explorer for quick handoff to native workflows.
    # --------------------------------------------------------
    def _onOpenActivePathInExplorer(self):
        if not self._active_panel:
            return

        path = self._active_panel.currentPath()
        if not path or not os.path.isdir(path):
            self._showStatus("No active folder to open.")
            return

        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", os.path.normpath(path)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self._showStatus(f"Opened in explorer: {path}")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open the active folder in the file explorer:\n{e}",
            )

    # --------------------------------------------------------
    # Properties Dialog
    # --------------------------------------------------------
    def _showProperties(self, entry):
        showFileProperties(entry, self)

    # --------------------------------------------------------
    # Drag-and-Drop from Panel
    # --------------------------------------------------------
    def _onDroppedFiles(self, file_paths, drop_target, is_copy):
        if is_copy:
            success, msg = copyFiles(file_paths, drop_target, self)
        else:
            success, msg = moveFiles(file_paths, drop_target, self)
        self._refreshBothPanels()
        self._showStatus(msg)

    # --------------------------------------------------------
    # About Dialog
    # --------------------------------------------------------
    def _onAbout(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME}\n"
            f"Version {APP_VERSION}\n\n"
            "A modern dual-pane file manager.\n\n"
            "Built with Python + PyQt5\n"
            "Dark theme inspired by Catppuccin Mocha"
        )

    # --------------------------------------------------------
    # Utility
    # --------------------------------------------------------
    def _refreshBothPanels(self):
        self._left_panel.refresh()
        self._right_panel.refresh()

    def _showStatus(self, message, timeout=5000):
        self._status_info.setText(message)
        QTimer.singleShot(timeout, lambda: self._status_info.setText("Ready"))

    def _updateStatusBar(self):
        if not self._active_panel:
            return
        entries = self._active_panel.selectedEntries()
        if entries:
            total_size = sum(e["size"] for e in entries if not e["is_dir"] and e["size"] >= 0)
            dirs = sum(1 for e in entries if e["is_dir"])
            files = len(entries) - dirs
            parts = []
            if files:
                parts.append(f"{files} file(s)")
            if dirs:
                parts.append(f"{dirs} folder(s)")
            from file_panel import formatFileSize
            parts.append(f"Total: {formatFileSize(total_size)}")
            self._status_info.setText(" | ".join(parts))
        else:
            self._status_info.setText("Ready")

    # --------------------------------------------------------
    # Window Close: Save State
    # --------------------------------------------------------
    def closeEvent(self, event):
        geo = self.geometry()
        self._settings.setSetting("window_geometry", {
            "x": geo.x(),
            "y": geo.y(),
            "width": geo.width(),
            "height": geo.height(),
        })

        self._settings.setPanelState("left", self._left_panel.getHistoryData())
        self._settings.setPanelState("right", self._right_panel.getHistoryData())

        bm_width = self._main_splitter.sizes()[0]
        if bm_width >= 100:
            self._settings.setState("bookmarks_panel_width", bm_width)

        structure = self._bookmarks_panel.getStructure()
        if structure is not None:
            self._settings.setBookmarksStructure(structure)

        current_tab = "libraries" if self._sidebar_tabs.currentIndex() == 1 else "bookmarks"
        self._settings.setSidebarState({
            "current_tab": current_tab,
        })

        self._settings.saveAll()
        event.accept()
