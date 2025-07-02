"""Support to emulate keyboard presses on host machine."""

from pykeyboard import PyKeyboard
import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, create_issue
from homeassistant.helpers.typing import ConfigType

DOMAIN = "keyboard"

TAP_KEY_SCHEMA = vol.Schema({})

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Listen for keyboard events."""
    create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{DOMAIN}",
        breaks_in_ha_version="2025.12.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_system_packages_yaml_integration",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Keyboard",
        },
    )

    keyboard = PyKeyboard()
    keyboard.special_key_assignment()

    hass.services.register(
        DOMAIN,
        SERVICE_VOLUME_UP,
        lambda service: keyboard.tap_key(keyboard.volume_up_key),
        schema=TAP_KEY_SCHEMA,
    )

    hass.services.register(
        DOMAIN,
        SERVICE_VOLUME_DOWN,
        lambda service: keyboard.tap_key(keyboard.volume_down_key),
        schema=TAP_KEY_SCHEMA,
    )

    hass.services.register(
        DOMAIN,
        SERVICE_VOLUME_MUTE,
        lambda service: keyboard.tap_key(keyboard.volume_mute_key),
        schema=TAP_KEY_SCHEMA,
    )

    hass.services.register(
        DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        lambda service: keyboard.tap_key(keyboard.media_play_pause_key),
        schema=TAP_KEY_SCHEMA,
    )

    hass.services.register(
        DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        lambda service: keyboard.tap_key(keyboard.media_next_track_key),
        schema=TAP_KEY_SCHEMA,
    )

    hass.services.register(
        DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        lambda service: keyboard.tap_key(keyboard.media_prev_track_key),
        schema=TAP_KEY_SCHEMA,
    )
    return True
