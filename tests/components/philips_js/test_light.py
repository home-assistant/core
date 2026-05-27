"""Tests for the Philips TV light platform."""

from homeassistant.components.philips_js.light import (
    _KNOWN_MENU_SETTINGS_FALLBACK,
    _menu_settings_for,
)


def test_menu_settings_for_uses_tv_data_when_present() -> None:
    """If the TV reports menuSettings, the fallback is not consulted."""
    style_data = {
        "styleName": "FOLLOW_VIDEO",
        "menuSettings": ["STANDARD", "GAME"],
    }
    assert _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=True) == [
        "STANDARD",
        "GAME",
    ]


def test_menu_settings_for_falls_back_on_quirked_firmware() -> None:
    """When the TV omits menuSettings and the firmware quirk is active, supply known defaults."""
    style_data = {"styleName": "FOLLOW_VIDEO"}
    result = _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=True)
    assert result == list(_KNOWN_MENU_SETTINGS_FALLBACK["FOLLOW_VIDEO"])
    assert "CINEMA" in result


def test_menu_settings_for_no_fallback_without_quirk() -> None:
    """When the quirk is inactive, missing menuSettings is not augmented.

    This avoids supplying fallbacks on TVs that legitimately do not expose
    these presets, which would surface non-functional effects in the dropdown.
    """
    style_data = {"styleName": "FOLLOW_VIDEO"}
    assert _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=False) == []


def test_menu_settings_for_unknown_style() -> None:
    """Styles not present in the fallback map yield an empty list."""
    style_data = {"styleName": "FOLLOW_UNKNOWN"}
    assert _menu_settings_for("FOLLOW_UNKNOWN", style_data, quirk_active=True) == []


def test_menu_settings_for_explicit_empty_list_falls_back() -> None:
    """A literal empty `menuSettings: []` should be treated the same as missing."""
    style_data = {"styleName": "FOLLOW_AUDIO", "menuSettings": []}
    result = _menu_settings_for("FOLLOW_AUDIO", style_data, quirk_active=True)
    assert result == list(_KNOWN_MENU_SETTINGS_FALLBACK["FOLLOW_AUDIO"])


def test_menu_settings_for_rejects_non_list_value() -> None:
    """A non-list `menuSettings` (e.g. a stray string) is treated as missing.

    Prevents iterating the characters of a string and generating bogus
    single-character effects.
    """
    style_data = {"styleName": "FOLLOW_VIDEO", "menuSettings": "STANDARD"}
    result = _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=True)
    assert result == list(_KNOWN_MENU_SETTINGS_FALLBACK["FOLLOW_VIDEO"])


def test_menu_settings_for_filters_non_string_items() -> None:
    """Non-string items inside `menuSettings` are filtered out, valid strings kept."""
    style_data = {
        "styleName": "FOLLOW_VIDEO",
        "menuSettings": ["STANDARD", None, 42, "GAME", {"nested": True}],
    }
    result = _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=False)
    assert result == ["STANDARD", "GAME"]


def test_menu_settings_for_falls_back_when_all_items_filtered() -> None:
    """If the entire list is non-string items, behave as if it were empty."""
    style_data = {"styleName": "FOLLOW_VIDEO", "menuSettings": [None, 42, {"x": 1}]}
    result = _menu_settings_for("FOLLOW_VIDEO", style_data, quirk_active=True)
    assert result == list(_KNOWN_MENU_SETTINGS_FALLBACK["FOLLOW_VIDEO"])


def test_known_menu_settings_fallback_covers_three_styles() -> None:
    """Each of the three known ambilight style families has a non-empty fallback.

    Asserts the contract (these styles are covered, with at least one entry
    each) rather than exact equality, so adding a fourth fallback in the
    future doesn't break this test.
    """
    for style in ("FOLLOW_VIDEO", "FOLLOW_AUDIO", "FOLLOW_COLOR"):
        assert style in _KNOWN_MENU_SETTINGS_FALLBACK
        assert _KNOWN_MENU_SETTINGS_FALLBACK[style]
