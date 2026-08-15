"""Theme palette and stylesheet unit tests (no display required for string checks)."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from theme import (
    COLORS,
    COLORS_LIGHT,
    getDarkThemeStylesheet,
    getLightThemeStylesheet,
    getStructuralStylesheet,
    getThemePalette,
    getUiMetrics,
    themeColor,
)


REQUIRED_SELECTORS = (
    "QDialog",
    "QRadioButton",
    "QSpinBox",
    "#compareDiffSummary",
    "#transferTaskRow",
    "#dialogHint",
    "#dialogSectionHeader",
    "#filePanelActive",
    "#accentButton",
)


class ThemeTests(unittest.TestCase):
    def test_light_palette_differs_from_dark(self):
        self.assertNotEqual(COLORS["base"], COLORS_LIGHT["base"])
        self.assertEqual(getThemePalette("light")["green"], COLORS_LIGHT["green"])
        self.assertEqual(getThemePalette("dark")["green"], COLORS["green"])

    def test_metrics_grow_with_density(self):
        compact = getUiMetrics(10, 70)
        comfortable = getUiMetrics(10, 115)
        self.assertLess(compact["dialog_min_w"], comfortable["dialog_min_w"])
        self.assertLess(compact["nav_bar_height"], comfortable["nav_bar_height"])
        self.assertIn("pane_narrow_px", compact)
        self.assertIn("splitter_handle", compact)

    def test_dark_and_light_stylesheets_include_roles(self):
        dark = getDarkThemeStylesheet(font_size_pt=10, metrics=getUiMetrics(10, 100))
        light = getLightThemeStylesheet(font_size_pt=10, metrics=getUiMetrics(10, 100))
        for sheet in (dark, light):
            for selector in REQUIRED_SELECTORS:
                self.assertIn(selector, sheet, selector)
        self.assertNotIn("#a6e3a1", light)

    def test_structural_stylesheet_keeps_focus_ring(self):
        sheet = getStructuralStylesheet(10, getUiMetrics(10, 100))
        self.assertIn("#filePanelActive", sheet)
        self.assertIn("#dialogSectionHeader", sheet)

    def test_theme_color_helper(self):
        self.assertEqual(themeColor("green", "light"), COLORS_LIGHT["green"])
        self.assertEqual(themeColor("green", "dark"), COLORS["green"])


if __name__ == "__main__":
    unittest.main()
