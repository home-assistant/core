"""Define services for the Apple TV integration."""

from __future__ import annotations

from pyatv.const import KeyboardFocusState
from pyatv.exceptions import NotSupportedError, ProtocolError
from pyatv.interface import AppleTV as AppleTVInterface
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_TEXT, DOMAIN

SERVICE_SET_KEYBOARD_TEXT = "set_keyboard_text"
SERVICE_SET_KEYBOARD_TEXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_TEXT): cv.string,
    }
)

SERVICE_APPEND_KEYBOARD_TEXT = "append_keyboard_text"
SERVICE_APPEND_KEYBOARD_TEXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_TEXT): cv.string,
    }
)

SERVICE_CLEAR_KEYBOARD_TEXT = "clear_keyboard_text"
SERVICE_CLEAR_KEYBOARD_TEXT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _get_atv(call: ServiceCall) -> AppleTVInterface:
    """Get the AppleTVInterface for a service call."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    atv: AppleTVInterface | None = entry.runtime_data.atv
    if atv is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )
    return atv


def _check_keyboard_focus(atv: AppleTVInterface) -> None:
    """Check that keyboard is focused on the device."""
    try:
        focus_state = atv.keyboard.text_focus_state
    except NotSupportedError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="keyboard_not_available",
        ) from err
    if focus_state != KeyboardFocusState.Focused:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="keyboard_not_focused",
        )


async def _async_set_keyboard_text(call: ServiceCall) -> None:
    """Set text in the keyboard input field on an Apple TV."""
    atv = _get_atv(call)
    _check_keyboard_focus(atv)
    try:
        await atv.keyboard.text_set(call.data[ATTR_TEXT])
    except ProtocolError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keyboard_error",
        ) from err


async def _async_append_keyboard_text(call: ServiceCall) -> None:
    """Append text to the keyboard input field on an Apple TV."""
    atv = _get_atv(call)
    _check_keyboard_focus(atv)
    try:
        await atv.keyboard.text_append(call.data[ATTR_TEXT])
    except ProtocolError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keyboard_error",
        ) from err


async def _async_clear_keyboard_text(call: ServiceCall) -> None:
    """Clear text in the keyboard input field on an Apple TV."""
    atv = _get_atv(call)
    _check_keyboard_focus(atv)
    try:
        await atv.keyboard.text_clear()
    except ProtocolError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keyboard_error",
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Apple TV integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_KEYBOARD_TEXT,
        _async_set_keyboard_text,
        schema=SERVICE_SET_KEYBOARD_TEXT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_KEYBOARD_TEXT,
        _async_append_keyboard_text,
        schema=SERVICE_APPEND_KEYBOARD_TEXT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_KEYBOARD_TEXT,
        _async_clear_keyboard_text,
        schema=SERVICE_CLEAR_KEYBOARD_TEXT_SCHEMA,
    )
