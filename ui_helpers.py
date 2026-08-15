"""
Shared dialog and label helpers used across settings, filters, and compare UIs.
Keeps objectNames and accessibility metadata consistent with theme.py.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from theme import getUiMetrics, themeColor


# ------------------------------------------------------------
# Function: currentUiMetrics
# Purpose: Metrics already computed by applyTheme, or a default set.
# ------------------------------------------------------------
def currentUiMetrics():
    app = QApplication.instance()
    metrics = getattr(app, "_ui_metrics", None) if app is not None else None
    if metrics:
        return metrics
    return getUiMetrics(10, 100)


# ------------------------------------------------------------
# Function: configureDialog
# Purpose: Title, help-button hide, metric-based minimum size,
#          and a resize that fits the parent window when possible.
# ------------------------------------------------------------
def configureDialog(dialog, title, min_w=None, min_h=None, wide=False):
    dialog.setWindowTitle(title)
    flags = dialog.windowFlags()
    try:
        from PyQt5.QtCore import Qt as _Qt
        dialog.setWindowFlags(flags & ~_Qt.WindowContextHelpButtonHint)
    except Exception:
        pass

    metrics = currentUiMetrics()
    width = int(
        min_w
        if min_w is not None
        else (
            metrics.get("dialog_wide_min_w", 640)
            if wide
            else metrics.get("dialog_min_w", 480)
        )
    )
    height = int(min_h if min_h is not None else metrics.get("dialog_min_h", 360))
    dialog.setMinimumWidth(max(360, min(width, 720)))

    parent = dialog.parentWidget()
    avail_h = 720
    avail_w = 900
    if parent is not None:
        win = parent.window()
        if win is not None:
            avail_h = max(360, win.height() - 48)
            avail_w = max(400, win.width() - 48)
    dialog.resize(min(width + 40, avail_w), min(max(height, 280), avail_h))
    return metrics


# ------------------------------------------------------------
# Function: sectionLabel / hintLabel
# ------------------------------------------------------------
def sectionLabel(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("dialogSectionHeader")
    return label


def hintLabel(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName("dialogHint")
    label.setWordWrap(True)
    return label


def errorLabel(text="", parent=None):
    label = QLabel(text, parent)
    label.setObjectName("dialogError")
    label.setWordWrap(True)
    label.setVisible(bool(text))
    return label


# ------------------------------------------------------------
# Function: setAccessible
# Purpose: Buddy + accessible name/description for a control.
# ------------------------------------------------------------
def setAccessible(widget, name, description=None, label=None):
    if widget is None:
        return
    widget.setAccessibleName(name)
    if description:
        widget.setAccessibleDescription(description)
    if label is not None and hasattr(label, "setBuddy"):
        label.setBuddy(widget)


# ------------------------------------------------------------
# Function: wrapScrollable
# Purpose: Put an inner widget in a QScrollArea that fills leftover
#          dialog space so action rows can stay pinned below.
# ------------------------------------------------------------
def wrapScrollable(inner_widget, parent=None):
    scroll = QScrollArea(parent)
    scroll.setObjectName("dialogScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setWidget(inner_widget)
    scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return scroll


def addScrollableBody(layout, inner_widget):
    scroll = wrapScrollable(inner_widget)
    layout.addWidget(scroll, 1)
    return scroll


# ------------------------------------------------------------
# Function: markAccentButton
# Purpose: Style the default/primary dialog button.
# ------------------------------------------------------------
def markAccentButton(button):
    if button is None:
        return
    button.setObjectName("accentButton")
    button.setDefault(True)
    button.setAutoDefault(True)


def markDestructiveButton(button):
    if button is None:
        return
    button.setObjectName("destructiveButton")


def accentButtonFromBox(button_box, role=QDialogButtonBox.Ok):
    button = button_box.button(role)
    markAccentButton(button)
    return button


# ------------------------------------------------------------
# Function: selectablePathLabel
# Purpose: Long paths stay selectable and wrap instead of clipping.
# ------------------------------------------------------------
def selectablePathLabel(text, parent=None):
    label = QLabel(text or "—", parent)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setObjectName("pathValueLabel")
    return label


# ------------------------------------------------------------
# Function: buildPathComparisonGrid
# Purpose: Shared Source/Destination (or Left/Right) comparison table.
# Input:  fields - list of (heading, key) rows under the two titles.
# Output: dict with grid, left_labels, right_labels.
# ------------------------------------------------------------
def buildPathComparisonGrid(left_title, right_title, fields, parent=None):
    grid = QGridLayout()
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(8)

    left_header = sectionLabel(left_title, parent)
    right_header = sectionLabel(right_title, parent)
    grid.addWidget(left_header, 0, 1)
    grid.addWidget(right_header, 0, 2)

    left_labels = {}
    right_labels = {}
    for index, (title, key) in enumerate(fields, start=1):
        heading = QLabel(title, parent)
        heading.setObjectName("dialogHint")
        grid.addWidget(heading, index, 0, Qt.AlignTop)
        left = selectablePathLabel("", parent)
        right = selectablePathLabel("", parent)
        grid.addWidget(left, index, 1, Qt.AlignTop)
        grid.addWidget(right, index, 2, Qt.AlignTop)
        left_labels[key] = left
        right_labels[key] = right

    return {
        "grid": grid,
        "left_labels": left_labels,
        "right_labels": right_labels,
    }


# ------------------------------------------------------------
# Function: previewItemColor
# Purpose: Theme-aware QColor for batch-rename preview rows.
# ------------------------------------------------------------
def previewItemColor(changed):
    from PyQt5.QtGui import QColor

    key = "green" if changed else "overlay0"
    return QColor(themeColor(key))
