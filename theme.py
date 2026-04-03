"""
Total Commander Clone - Dark Theme Stylesheet
Provides a modern, flat dark theme using Qt Style Sheets (QSS).
Color palette inspired by Catppuccin Mocha.
"""

from PyQt5.QtWidgets import QStyleFactory

# ------------------------------------------------------------
# Color Constants
# ------------------------------------------------------------
COLORS = {
    "base":        "#1e1e2e",
    "mantle":      "#181825",
    "crust":       "#11111b",
    "surface0":    "#313244",
    "surface1":    "#45475a",
    "surface2":    "#585b70",
    "overlay0":    "#6c7086",
    "overlay1":    "#7f849c",
    "text":        "#cdd6f4",
    "subtext0":    "#a6adc8",
    "subtext1":    "#bac2de",
    "blue":        "#89b4fa",
    "lavender":    "#b4befe",
    "sapphire":    "#74c7ec",
    "green":       "#a6e3a1",
    "red":         "#f38ba8",
    "peach":       "#fab387",
    "yellow":      "#f9e2af",
    "mauve":       "#cba6f7",
    "rosewater":   "#f5e0dc",
    "panel_bg":    "#24243a",
    "active_border": "#7aa2f7",
    "panel_focus_ring": "#ff9f43",
    "hover":       "#2d2d44",
    "selection":   "#394060",
    "border":      "#45475a",
    "button":      "#363654",
    "button_hover": "#45457a",
    "button_press": "#52528a",
    "input_bg":    "#2a2a42",
    "scrollbar_bg": "#1e1e2e",
    "scrollbar_handle": "#45475a",
    "scrollbar_hover":  "#585b70",
}


# ------------------------------------------------------------
# Function: getDarkThemeStylesheet
# Purpose: Returns the complete QSS stylesheet string for the
#          dark theme applied to the entire application.
# ------------------------------------------------------------
def getDarkThemeStylesheet(base_path=None):
    c = COLORS
    return f"""

    /* ====================================================== */
    /* Global Widget Defaults                                  */
    /* ====================================================== */
    QWidget {{
        background-color: {c['base']};
        color: {c['text']};
        font-family: "Segoe UI", "Roboto", sans-serif;
        border: none;
    }}

    /* ====================================================== */
    /* Main Window                                             */
    /* ====================================================== */
    QMainWindow {{
        background-color: {c['crust']};
    }}

    /* ====================================================== */
    /* Menu Bar                                                */
    /* ====================================================== */
    QMenuBar {{
        background-color: {c['mantle']};
        color: {c['text']};
        border-bottom: 1px solid {c['border']};
        padding: 2px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }}
    QMenuBar::item:selected {{
        background-color: {c['surface0']};
    }}

    /* ====================================================== */
    /* Menus (dropdowns)                                       */
    /* ====================================================== */
    QMenu {{
        background-color: {c['mantle']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 30px 8px 20px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {c['selection']};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c['border']};
        margin: 4px 10px;
    }}
    QMenu::icon {{
        padding-left: 6px;
    }}

    /* ====================================================== */
    /* Toolbar                                                 */
    /* ====================================================== */
    QToolBar {{
        background-color: {c['mantle']};
        border-bottom: 1px solid {c['border']};
        padding: 3px 6px;
        spacing: 4px;
    }}
    QToolBar::separator {{
        width: 1px;
        background: {c['border']};
        margin: 4px 6px;
    }}
    QToolButton {{
        background-color: transparent;
        color: {c['text']};
        border: 1px solid transparent;
        border-radius: 5px;
        padding: 5px 10px;
        font-size: 13px;
    }}
    QToolButton:hover {{
        background-color: {c['hover']};
        border: 1px solid {c['border']};
    }}
    QToolButton:pressed {{
        background-color: {c['surface0']};
    }}
    QToolButton:checked {{
        background-color: {c['selection']};
        border: 1px solid {c['active_border']};
    }}

    /* ====================================================== */
    /* Push Buttons                                            */
    /* ====================================================== */
    QPushButton {{
        background-color: {c['button']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 16px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {c['button_hover']};
        border: 1px solid {c['active_border']};
    }}
    QPushButton:pressed {{
        background-color: {c['button_press']};
    }}
    QPushButton:disabled {{
        background-color: {c['surface0']};
        color: {c['overlay0']};
        border: 1px solid {c['surface0']};
    }}
    QPushButton#accentButton {{
        background-color: {c['active_border']};
        color: {c['crust']};
        font-weight: bold;
    }}
    QPushButton#accentButton:hover {{
        background-color: {c['blue']};
    }}
    QPushButton#navButton {{
        padding: 4px;
        min-width: 30px;
    }}
    QPushButton#navButton:focus {{
        border: 1px solid {c['border']};
        background-color: {c['button']};
    }}
    QPushButton#navButton:default {{
        border: 1px solid {c['border']};
        background-color: {c['button']};
    }}

    /* ====================================================== */
    /* Line Edits / Inputs                                     */
    /* ====================================================== */
    QLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 10px;
        selection-background-color: {c['selection']};
    }}
    QLineEdit:focus {{
        border: 1px solid {c['active_border']};
    }}
    QLineEdit:read-only {{
        background-color: {c['surface0']};
    }}

    /* ====================================================== */
    /* Table View (File Listing)                               */
    /* ====================================================== */
    QTableView {{
        background-color: {c['panel_bg']};
        alternate-background-color: {c['base']};
        color: {c['text']};
        gridline-color: {c['surface0']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        selection-background-color: {c['selection']};
        selection-color: {c['text']};
        outline: none;
    }}
    QTableView::item {{
        padding: 4px 8px;
        border: none;
    }}
    QTableView::item:hover {{
        background-color: {c['hover']};
    }}
    QTableView::item:selected {{
        background-color: {c['selection']};
        color: {c['text']};
    }}
    QTableView::item:focus {{
        outline: none;
        border: none;
    }}

    /* ====================================================== */
    /* Header View (Table Column Headers)                      */
    /* ====================================================== */
    QHeaderView {{
        background-color: {c['mantle']};
        border: none;
    }}
    QHeaderView::section {{
        background-color: {c['mantle']};
        color: {c['subtext1']};
        border: none;
        border-right: 1px solid {c['surface0']};
        border-bottom: 1px solid {c['border']};
        padding: 6px 10px;
        font-weight: bold;
    }}
    QHeaderView::section:hover {{
        background-color: {c['surface0']};
        color: {c['text']};
    }}
    QHeaderView::section:pressed {{
        background-color: {c['surface1']};
    }}

    /* ====================================================== */
    /* Scroll Bars                                             */
    /* ====================================================== */
    QScrollBar:vertical {{
        background: {c['scrollbar_bg']};
        width: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scrollbar_handle']};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['scrollbar_hover']};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        background: {c['scrollbar_bg']};
        height: 10px;
        margin: 0;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['scrollbar_handle']};
        min-width: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['scrollbar_hover']};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
    }}

    /* ====================================================== */
    /* Splitter                                                */
    /* ====================================================== */
    QSplitter::handle {{
        background-color: {c['border']};
        width: 2px;
    }}
    QSplitter::handle:hover {{
        background-color: {c['active_border']};
    }}

    /* ====================================================== */
    /* Status Bar                                              */
    /* ====================================================== */
    QStatusBar {{
        background-color: {c['mantle']};
        color: {c['subtext0']};
        border-top: 1px solid {c['border']};
        padding: 2px 8px;
    }}
    QStatusBar::item {{
        border: none;
    }}

    /* ====================================================== */
    /* Tooltips                                                */
    /* ====================================================== */
    QToolTip {{
        background-color: {c['surface0']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 4px 8px;
    }}

    /* ====================================================== */
    /* Progress Bar                                            */
    /* ====================================================== */
    QProgressBar {{
        background-color: {c['surface0']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        text-align: center;
        color: {c['text']};
        height: 20px;
    }}
    QProgressBar::chunk {{
        background-color: {c['active_border']};
        border-radius: 5px;
    }}

    /* ====================================================== */
    /* Dialog                                                  */
    /* ====================================================== */
    QDialog {{
        background-color: {c['base']};
    }}

    /* ====================================================== */
    /* Message Box                                             */
    /* ====================================================== */
    QMessageBox {{
        background-color: {c['base']};
    }}
    QMessageBox QLabel {{
        color: {c['text']};
    }}

    /* ====================================================== */
    /* Input Dialog                                            */
    /* ====================================================== */
    QInputDialog {{
        background-color: {c['base']};
    }}

    /* ====================================================== */
    /* Labels                                                  */
    /* ====================================================== */
    QLabel {{
        color: {c['text']};
        background: transparent;
    }}
    QLabel#panelLabel {{
        color: {c['subtext0']};
        font-size: 11px;
    }}
    QLabel#statusLabel {{
        color: {c['subtext0']};
    }}

    /* ====================================================== */
    /* Group Box                                               */
    /* ====================================================== */
    QGroupBox {{
        border: 1px solid {c['border']};
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 16px;
        color: {c['text']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        color: {c['subtext1']};
    }}

    /* ====================================================== */
    /* Combo Box                                               */
    /* ====================================================== */
    QComboBox {{
        background-color: {c['input_bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 10px;
    }}
    QComboBox:hover {{
        border: 1px solid {c['active_border']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c['mantle']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['selection']};
        border-radius: 4px;
    }}

    /* ====================================================== */
    /* Check Box                                               */
    /* ====================================================== */
    QCheckBox {{
        color: {c['text']};
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['border']};
        border-radius: 4px;
        background-color: {c['input_bg']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['active_border']};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c['active_border']};
        border-color: {c['active_border']};
    }}

    /* ====================================================== */
    /* Tab Widget (for possible future use)                    */
    /* ====================================================== */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        border-radius: 6px;
        background-color: {c['base']};
    }}
    QTabBar::tab {{
        background-color: {c['mantle']};
        color: {c['subtext0']};
        border: 1px solid {c['border']};
        border-bottom: none;
        padding: 8px 16px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        background-color: {c['base']};
        color: {c['text']};
        border-bottom: 2px solid {c['active_border']};
    }}
    QTabBar::tab:hover {{
        background-color: {c['surface0']};
        color: {c['text']};
    }}

    /* ====================================================== */
    /* Custom Panel Frame (applied via objectName)             */
    /* ====================================================== */
    QWidget#filePanel {{
        background-color: {c['panel_bg']};
        border: 1px solid {c['overlay0']};
        border-radius: 8px;
    }}
    QWidget#filePanelActive {{
        background-color: {c['panel_bg']};
        border: 1px solid {c['panel_focus_ring']};
        border-radius: 8px;
    }}

    /* ====================================================== */
    /* Bottom Button Bar                                       */
    /* ====================================================== */
    QFrame#bottomBar {{
        background-color: {c['mantle']};
        border-top: 1px solid {c['border']};
    }}
    QFrame#bottomBar QPushButton {{
        background-color: transparent;
        border: 1px solid {c['border']};
        border-radius: 4px;
        padding: 5px 14px;
        font-weight: bold;
        color: {c['subtext1']};
    }}
    QFrame#bottomBar QPushButton:hover {{
        background-color: {c['button_hover']};
        color: {c['text']};
        border-color: {c['active_border']};
    }}

    /* ====================================================== */
    /* Center Panel (directional copy/move buttons)            */
    /* ====================================================== */
    QFrame#centerPanel {{
        background-color: {c['mantle']};
        border: none;
        min-width: 48px;
        max-width: 48px;
    }}
    QFrame#centerPanel QPushButton {{
        background-color: {c['button']};
        color: {c['subtext1']};
        border: 1px solid {c['border']};
        border-radius: 5px;
        padding: 4px 2px;
        font-size: 18px;
        font-weight: bold;
        min-height: 36px;
    }}
    QFrame#centerPanel QPushButton:hover {{
        background-color: {c['button_hover']};
        color: {c['text']};
        border-color: {c['active_border']};
    }}
    QFrame#centerPanel QPushButton:pressed {{
        background-color: {c['button_press']};
    }}
    QFrame#centerPanel QLabel {{
        color: {c['overlay0']};
        font-size: 9px;
    }}

    /* ====================================================== */
    /* Bookmarks panel tree                                     */
    /* ====================================================== */
    QTreeWidget {{
        background-color: {c['panel_bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        outline: none;
    }}
    QTreeWidget::item {{
        padding: 4px 6px;
    }}
    QTreeWidget::item:hover {{
        background-color: {c['hover']};
    }}
    QTreeWidget::item:selected {{
        background-color: {c['selection']};
        color: {c['text']};
    }}
    /* Do not style ::branch so the default expand/collapse arrows remain visible. */

    QPushButton#bookmarksToolButton {{
        padding: 2px 8px;
        font-size: 11px;
        min-height: 22px;
    }}

    /* ====================================================== */
    /* Drive selector combo (file panel nav bar)                */
    /* ====================================================== */
    QComboBox#driveCombo {{
        min-width: 58px;
        max-width: 58px;
        min-height: 28px;
        max-height: 28px;
        padding: 0;
        font-weight: bold;
        font-size: 13px;
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }}
    QComboBox#driveCombo::drop-down {{
        width: 0;
        border: none;
    }}
    QComboBox#driveCombo QAbstractItemView {{
        text-align: center;
    }}
    QComboBox#driveCombo QLineEdit {{
        background: transparent;
        padding: 0 4px;
        text-align: center;
    }}
    QLabel#driveArrow {{
        color: {c['text']};
        font-size: 8px;
        padding: 0;
        margin: 0;
        background-color: {c['surface0']};
        border: 1px solid {c['border']};
        border-left: none;
        border-top-right-radius: 5px;
        border-bottom-right-radius: 5px;
        min-width: 14px;
        max-width: 14px;
        qproperty-alignment: AlignCenter;
    }}

    /* ====================================================== */
    /* Batch Rename Preview Table                              */
    /* ====================================================== */
    QTableWidget#batchPreview {{
        background-color: {c['panel_bg']};
        alternate-background-color: {c['base']};
        color: {c['text']};
        gridline-color: {c['surface0']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        selection-background-color: {c['selection']};
    }}
    QTableWidget#batchPreview::item {{
        padding: 3px 6px;
    }}
    QLabel#batchChanged {{
        color: {c['green']};
    }}
    QLabel#batchUnchanged {{
        color: {c['overlay0']};
    }}

    /* ====================================================== */
    /* Library Browser Panel                                    */
    /* ====================================================== */
    QPushButton#libraryToolButton {{
        padding: 2px 8px;
        font-size: 11px;
        min-height: 22px;
    }}

    QListWidget {{
        background-color: {c['panel_bg']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 4px 6px;
    }}
    QListWidget::item:hover {{
        background-color: {c['hover']};
    }}
    QListWidget::item:selected {{
        background-color: {c['selection']};
        color: {c['text']};
    }}
    """


def applyTheme(app, theme_mode):
    mode = (theme_mode or "dark").lower()

    if mode == "dark":
        app.setStyleSheet(getDarkThemeStylesheet())
        return

    app.setStyleSheet("")

    if mode == "light":
        fusion_style = QStyleFactory.create("Fusion")
        if fusion_style is not None:
            app.setStyle(fusion_style)
            app.setPalette(fusion_style.standardPalette())
        return

    system_style_name = getattr(app, "_system_style_name", "")
    if system_style_name:
        system_style = QStyleFactory.create(system_style_name)
        if system_style is not None:
            app.setStyle(system_style)
    system_palette = getattr(app, "_system_palette", None)
    if system_palette is not None:
        app.setPalette(system_palette)
