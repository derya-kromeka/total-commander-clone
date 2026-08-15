"""
Responsive layout tiers for the dual-pane file manager.

Tiers are derived from current pane/window size and UI density metrics.
Callers apply chrome compaction; table column locks stay in FilePanel.
"""

from enum import Enum


# ------------------------------------------------------------
# Enum: LayoutTier
# Purpose: Width-based density of chrome (toolbar, nav, F-keys).
# ------------------------------------------------------------
class LayoutTier(Enum):
    CRITICAL = "critical"
    NARROW = "narrow"
    MEDIUM = "medium"
    COMFORTABLE = "comfortable"
    WIDE = "wide"


# ------------------------------------------------------------
# Enum: HeightTier
# Purpose: Vertical compaction (center labels, transfers bar).
# ------------------------------------------------------------
class HeightTier(Enum):
    SHORT = "short"
    NORMAL = "normal"
    TALL = "tall"


_TIER_RANK = {
    LayoutTier.CRITICAL: 0,
    LayoutTier.NARROW: 1,
    LayoutTier.MEDIUM: 2,
    LayoutTier.COMFORTABLE: 3,
    LayoutTier.WIDE: 4,
}


def scaledThreshold(base_px, metrics):
    """Scale a 100%-density pixel threshold by current layout_scale."""
    scale = 1.0
    if metrics:
        scale = float(metrics.get("layout_scale", 1.0) or 1.0)
    return max(1, int(round(base_px * scale)))


def layoutTierForPane(pane_w, metrics=None):
    """
    Classify a single file-pane content width.
    Falls back to metric keys when present, else 100% defaults.
    """
    if metrics:
        critical = int(metrics.get("pane_critical_px", scaledThreshold(340, metrics)))
        narrow = int(metrics.get("pane_narrow_px", scaledThreshold(430, metrics)))
        medium = int(metrics.get("pane_medium_px", scaledThreshold(520, metrics)))
        comfortable = int(metrics.get("pane_comfortable_px", scaledThreshold(680, metrics)))
    else:
        critical, narrow, medium, comfortable = 340, 430, 520, 680
    w = max(0, int(pane_w or 0))
    if w < critical:
        return LayoutTier.CRITICAL
    if w < narrow:
        return LayoutTier.NARROW
    if w < medium:
        return LayoutTier.MEDIUM
    if w < comfortable:
        return LayoutTier.COMFORTABLE
    return LayoutTier.WIDE


def layoutTierForWindow(window_w, metrics=None):
    """Classify overall window width for toolbar / F-key bar."""
    if metrics:
        narrow = int(metrics.get("window_narrow_px", scaledThreshold(1020, metrics)))
        medium = int(metrics.get("window_medium_px", scaledThreshold(1200, metrics)))
        wide = int(metrics.get("window_wide_px", scaledThreshold(1600, metrics)))
    else:
        narrow, medium, wide = 1020, 1200, 1600
    w = max(0, int(window_w or 0))
    if w < 900:
        return LayoutTier.CRITICAL
    if w < narrow:
        return LayoutTier.NARROW
    if w < medium:
        return LayoutTier.MEDIUM
    if w < wide:
        return LayoutTier.COMFORTABLE
    return LayoutTier.WIDE


def layoutTierForHeight(content_h, metrics=None):
    """Classify usable central-widget height."""
    short = 520
    if metrics:
        short = int(metrics.get("content_short_h", scaledThreshold(520, metrics)))
    h = max(0, int(content_h or 0))
    if h < short:
        return HeightTier.SHORT
    if h < short + 200:
        return HeightTier.NORMAL
    return HeightTier.TALL


def tierAtMost(tier, maximum):
    """True if tier is at or denser than maximum (e.g. NARROW includes CRITICAL)."""
    return _TIER_RANK.get(tier, 2) <= _TIER_RANK.get(maximum, 2)


def combineTiers(window_tier, pane_tier):
    """Use the denser of two tiers when applying shared chrome."""
    if _TIER_RANK.get(pane_tier, 2) < _TIER_RANK.get(window_tier, 2):
        return pane_tier
    return window_tier
