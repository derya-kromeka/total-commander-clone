"""Layout-tier and unlocked-column reflow tests."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from theme import getUiMetrics
from ui_layout_policy import (
    HeightTier,
    LayoutTier,
    layoutTierForHeight,
    layoutTierForPane,
    layoutTierForWindow,
    tierAtMost,
)


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class LayoutTierTests(unittest.TestCase):
    def test_pane_tiers_order(self):
        metrics = getUiMetrics(10, 100)
        self.assertEqual(layoutTierForPane(200, metrics), LayoutTier.CRITICAL)
        self.assertEqual(layoutTierForPane(400, metrics), LayoutTier.NARROW)
        self.assertEqual(layoutTierForPane(500, metrics), LayoutTier.MEDIUM)
        self.assertEqual(layoutTierForPane(900, metrics), LayoutTier.WIDE)

    def test_window_and_height_tiers(self):
        metrics = getUiMetrics(10, 100)
        self.assertTrue(tierAtMost(layoutTierForWindow(800, metrics), LayoutTier.NARROW))
        self.assertEqual(layoutTierForHeight(400, metrics), HeightTier.SHORT)
        self.assertNotEqual(layoutTierForHeight(900, metrics), HeightTier.SHORT)

    def test_unlocked_columns_reflow(self):
        _app()
        from file_panel import FilePanel

        panel = FilePanel("left")
        panel.resize(800, 500)
        panel.show()
        QApplication.processEvents()
        panel._fitColumnsToViewport()
        panel._column_width_locked["name"] = True
        panel._locked_column_width_px["name"] = 180
        panel._table.setColumnWidth(0, 180)
        wide = max(1, panel._table.viewport().width())
        panel._table.setColumnWidth(1, 80)
        panel._table.setColumnWidth(2, 80)
        panel._table.setColumnWidth(3, 140)
        panel._fitColumnsToViewport()
        self.assertEqual(panel._table.columnWidth(0), panel._locked_column_width_px["name"])
        unlocked_sum = sum(
            panel._table.columnWidth(c) for c in range(1, 4) if not panel._table.isColumnHidden(c)
        )
        self.assertGreater(unlocked_sum, 0)
        total = sum(
            panel._table.columnWidth(c)
            for c in range(panel._source_model.columnCount())
            if not panel._table.isColumnHidden(c)
        )
        self.assertLessEqual(abs(total - wide), 8)
        panel.close()


if __name__ == "__main__":
    unittest.main()
