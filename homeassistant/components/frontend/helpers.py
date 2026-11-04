"""Helpers for the frontend integration."""

import logging
from typing import Any

import probatio

from homeassistant.const import EVENT_THEMES_UPDATED
from homeassistant.core import HomeAssistant, async_get_hass, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_dumps_sorted
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

CONF_NAME_DARK = "name_dark"

CONF_THEMES = "themes"

CONF_THEMES_MODES = "modes"

CONF_THEMES_LIGHT = "light"

CONF_THEMES_DARK = "dark"

DEFAULT_THEME_COLOR = "#2980b9"

THEMES_SAVE_DELAY = 60

DATA_THEMES_STORE: HassKey[Store] = HassKey("frontend_themes_store")

DATA_THEMES: HassKey[dict[str, Any]] = HassKey("frontend_themes")

DATA_DEFAULT_THEME = "frontend_default_theme"

DATA_DEFAULT_DARK_THEME = "frontend_default_dark_theme"

DEFAULT_THEME = "default"

VALUE_NO_THEME = "none"

PRIMARY_COLOR = "primary-color"

LEGACY_THEME_SCHEMA = probatio.Any(
    # Legacy theme scheme
    {cv.string: cv.string},
    # New extended schema with mode support
    {
        # Theme variables that apply to all modes
        cv.string: cv.string,
        # Mode specific theme variables
        probatio.Optional(CONF_THEMES_MODES): probatio.Schema(
            {
                probatio.Optional(CONF_THEMES_LIGHT): probatio.Schema(
                    {cv.string: cv.string}
                ),
                probatio.Optional(CONF_THEMES_DARK): probatio.Schema(
                    {cv.string: cv.string}
                ),
            }
        ),
    },
)

THEME_SCHEMA = probatio.Schema(
    {
        # Theme variables that apply to all modes
        cv.string: cv.string,
        # Mode specific theme variables
        probatio.Optional(CONF_THEMES_MODES): probatio.All(
            {
                probatio.Optional(CONF_THEMES_LIGHT): probatio.Schema(
                    {cv.string: cv.string}
                ),
                probatio.Optional(CONF_THEMES_DARK): probatio.Schema(
                    {cv.string: cv.string}
                ),
            },
            probatio.AtLeastOne(CONF_THEMES_LIGHT, CONF_THEMES_DARK),
        ),
    }
)


def validate_themes(themes: dict) -> dict[str, Any]:
    """Validate themes."""
    validated_themes = {}
    for theme_name, theme in themes.items():
        theme_name = cv.string(theme_name)
        LEGACY_THEME_SCHEMA(theme)

        try:
            validated_themes[theme_name] = THEME_SCHEMA(theme)
        except probatio.Invalid as err:
            _LOGGER.error("Theme %s is invalid: %s", theme_name, err)

    return validated_themes


class Manifest:
    """Manage the manifest.json contents."""

    def __init__(self, data: dict) -> None:
        """Init the manifest manager."""
        self.manifest = data
        self._serialize()

    def __getitem__(self, key: str) -> Any:
        """Return an item in the manifest."""
        return self.manifest[key]

    @property
    def json(self) -> str:
        """Return the serialized manifest."""
        return self._serialized

    def _serialize(self) -> None:
        self._serialized = json_dumps_sorted(self.manifest)

    def update_key(self, key: str, val: str) -> None:
        """Add a keyval to the manifest.json."""
        self.manifest[key] = val
        self._serialize()


MANIFEST_JSON = Manifest(
    {
        "background_color": "#FFFFFF",
        "description": (
            "Home automation platform that puts local control and privacy first."
        ),
        "dir": "ltr",
        "display": "standalone",
        "icons": [
            {
                "src": f"/static/icons/favicon-{size}x{size}.png",
                "sizes": f"{size}x{size}",
                "type": "image/png",
                "purpose": "any",
            }
            for size in (192, 384, 512, 1024)
        ]
        + [
            {
                "src": f"/static/icons/maskable_icon-{size}x{size}.png",
                "sizes": f"{size}x{size}",
                "type": "image/png",
                "purpose": "maskable",
            }
            for size in (48, 72, 96, 128, 192, 384, 512)
        ],
        "screenshots": [
            {
                "src": "/static/images/screenshots/screenshot-1.png",
                "sizes": "413x792",
                "type": "image/png",
            }
        ],
        "lang": "en-US",
        "name": "Home Assistant",
        "short_name": "Home Assistant",
        "start_url": "/?homescreen=1",
        "id": "/?homescreen=1",
        "theme_color": DEFAULT_THEME_COLOR,
        "prefer_related_applications": True,
        "related_applications": [
            {"platform": "play", "id": "io.homeassistant.companion.android"}
        ],
    }
)


def validate_selected_theme(theme: str) -> str:
    """Validate that a user selected theme is a valid theme."""
    if theme in (DEFAULT_THEME, VALUE_NO_THEME):
        return theme
    hass = async_get_hass()
    if theme not in hass.data[DATA_THEMES]:
        raise probatio.Invalid(f"Theme {theme} not found")
    return theme


@callback
def async_update_theme_and_fire_event(hass: HomeAssistant) -> None:
    """Update theme_color in manifest."""
    name = hass.data[DATA_DEFAULT_THEME]
    themes = hass.data[DATA_THEMES]
    if name != DEFAULT_THEME:
        MANIFEST_JSON.update_key(
            "theme_color",
            themes[name].get(
                "app-header-background-color",
                themes[name].get(PRIMARY_COLOR, DEFAULT_THEME_COLOR),
            ),
        )
    else:
        MANIFEST_JSON.update_key("theme_color", DEFAULT_THEME_COLOR)
    hass.bus.async_fire(EVENT_THEMES_UPDATED)
