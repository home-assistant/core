"""Version-based feature availability for Kiosker integration."""

from __future__ import annotations

import logging

from packaging import version

_LOGGER = logging.getLogger(__name__)

# Supported feature categories
FEATURE_CATEGORIES = ("sensors", "switches", "services")


def _process_added_features(available: dict[str, list[str]], features: dict) -> None:
    """Process added features for a version."""
    if "added" not in features:
        return

    for category in FEATURE_CATEGORIES:
        if category in features["added"]:
            for feature in features["added"][category]:
                if feature not in available[category]:
                    available[category].append(feature)


def _process_removed_features(
    available: dict[str, list[str]], features: dict, ver_str: str
) -> None:
    """Process removed features for a version."""
    if "removed" not in features:
        return

    for category in FEATURE_CATEGORIES:
        if category in features["removed"]:
            for feature in features["removed"][category]:
                if feature in available[category]:
                    available[category].remove(feature)
                else:
                    _LOGGER.warning(
                        "Attempted to remove non-existent %s feature '%s' in version %s",
                        category,
                        feature,
                        ver_str,
                    )


# Version-based feature availability
VERSION_FEATURES = {
    "2025.9.1": {  # Initial supported version
        "added": {
            "sensors": [
                "batteryLevel",
                "batteryState",
                "lastInteraction",
                "lastMotion",
                "lastUpdate",
                "blackoutState",
                "screensaverVisibility",
            ],
            "switches": ["disable_screensaver"],
            "services": [
                "navigate_url",
                "navigate_refresh",
                "navigate_home",
                "navigate_backward",
                "navigate_forward",
                "print",
                "clear_cookies",
                "clear_cache",
                "screensaver_interact",
                "blackout_set",
                "blackout_clear",
            ],
        }
    },
    "2026.1.1": {"removed": {"sensors": ["batteryState"]}},
}


def get_available_features(app_version: str) -> dict[str, list[str]]:
    """Get features available for given app version with fallback."""
    if not app_version or not app_version.strip():
        _LOGGER.error("Invalid app version provided: %s", app_version)
        return {category: [] for category in FEATURE_CATEGORIES}

    try:
        app_ver = version.parse(app_version.strip())
    except (ValueError, TypeError) as exc:
        _LOGGER.error("Failed to parse app version '%s': %s", app_version, exc)
        return {category: [] for category in FEATURE_CATEGORIES}

    # Initialize available features
    available: dict[str, list[str]] = {category: [] for category in FEATURE_CATEGORIES}

    # Sort version keys to process in chronological order using semantic versioning
    sorted_versions = sorted(VERSION_FEATURES.keys(), key=version.parse)

    # Process all versions <= app_version
    for ver_str in sorted_versions:
        if app_ver >= version.parse(ver_str):
            features = VERSION_FEATURES[ver_str]
            _process_added_features(available, features)
            _process_removed_features(available, features, ver_str)
        else:
            break  # Stop when we hit a version higher than app

    return available


def is_version_supported(app_version: str) -> bool:
    """Check if app version meets minimum requirements."""
    if not app_version or not app_version.strip():
        return False

    try:
        app_ver = version.parse(app_version.strip())
        min_version = min(VERSION_FEATURES.keys(), key=version.parse)
        return app_ver >= version.parse(min_version)
    except (ValueError, TypeError) as exc:
        _LOGGER.error("Failed to validate version '%s': %s", app_version, exc)
        return False


def get_minimum_version() -> str:
    """Get the minimum supported app version."""
    return min(VERSION_FEATURES.keys(), key=version.parse)
