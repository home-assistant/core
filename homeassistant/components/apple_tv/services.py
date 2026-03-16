"""Define services for the Apple TV integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyatv.const import KeyboardFocusState
from pyatv.exceptions import NotSupportedError, ProtocolError
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_TEXT, DOMAIN

if TYPE_CHECKING:
    from . import AppleTVManager

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


def _get_manager(call: ServiceCall) -> AppleTVManager:
    """Get the AppleTVManager for a service call."""
    entry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    manager: AppleTVManager = entry.runtime_data
    if manager.atv is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )
    return manager


def _check_keyboard_focus(manager: AppleTVManager) -> None:
    """Check that keyboard is focused on the device."""
    try:
        focus_state = manager.atv.keyboard.text_focus_state  # type: ignore[union-attr]
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
    manager = _get_manager(call)
    _check_keyboard_focus(manager)
    try:
        await manager.atv.keyboard.text_set(call.data[ATTR_TEXT])  # type: ignore[union-attr]
    except ProtocolError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keyboard_error",
        ) from err


async def _async_append_keyboard_text(call: ServiceCall) -> None:
    """Append text to the keyboard input field on an Apple TV."""
    manager = _get_manager(call)
    _check_keyboard_focus(manager)
    try:
        await manager.atv.keyboard.text_append(call.data[ATTR_TEXT])  # type: ignore[union-attr]
    except ProtocolError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keyboard_error",
        ) from err


async def _async_clear_keyboard_text(call: ServiceCall) -> None:
    """Clear text in the keyboard input field on an Apple TV."""
    manager = _get_manager(call)
    _check_keyboard_focus(manager)
    try:
        await manager.atv.keyboard.text_clear()  # type: ignore[union-attr]
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
