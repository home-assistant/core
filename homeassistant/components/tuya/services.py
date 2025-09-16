"""Support for the Abode Security System."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import TuyaConfigEntry

SEND_TEXT_COMMAND = "send_text_command"

ATTR_CODE = "code"
ATTR_VALUE = "value"


SEND_TEXT_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CODE): cv.string,
        vol.Required(ATTR_VALUE): cv.string,
    }
)


@callback
def _async_get_device(
    call: ServiceCall,
) -> tuple[dr.DeviceEntry, TuyaConfigEntry]:
    """Get the registry device and config entry related to a service call."""
    device_registry = dr.async_get(call.hass)
    device_id = call.data[ATTR_DEVICE_ID]
    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    entry: TuyaConfigEntry | None
    for entry_id in device_entry.config_entries:
        if (entry := call.hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"entry": entry.title},
                )

            return device_entry, entry

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"device_id": device_id},
    )


async def _async_send_device_command(call: ServiceCall) -> None:
    """Send Tuya device command."""
    device_entry, config_entry = _async_get_device(call)
    manager = config_entry.runtime_data.manager
    tuya_device_id = next(
        (
            key
            for key in manager.device_map
            if (DOMAIN, key) in device_entry.identifiers
        ),
    )
    commands = [
        {
            "code": call.data[ATTR_CODE],
            "value": call.data[ATTR_VALUE],
        }
    ]

    LOGGER.debug("Sending commands for device %s: %s", tuya_device_id, commands)
    await call.hass.async_add_executor_job(
        config_entry.runtime_data.manager.send_commands,
        tuya_device_id,
        commands,
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    hass.services.async_register(
        DOMAIN,
        SEND_TEXT_COMMAND,
        _async_send_device_command,
        schema=SEND_TEXT_COMMAND_SCHEMA,
    )
