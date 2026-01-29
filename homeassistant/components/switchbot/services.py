"""Services for the SwitchBot integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, SupportedModels
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator

SERVICE_ADD_PASSWORD = "add_password"

ATTR_PASSWORD = "password"

_PASSWORD_VALIDATOR = vol.All(cv.string, cv.matches_regex(r"^\d{6,12}$"))

SCHEMA_ADD_PASSWORD_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PASSWORD): _PASSWORD_VALIDATOR,
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_get_switchbot_entry_for_device_id(
    hass: HomeAssistant, device_id: str
) -> SwitchbotConfigEntry:
    """Return the loaded SwitchBot config entry for a device id."""
    device_registry = dr.async_get(hass)
    if not (device_entry := device_registry.async_get(device_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    entries = [
        hass.config_entries.async_get_entry(entry_id)
        for entry_id in device_entry.config_entries
    ]
    switchbot_entries = [
        entry for entry in entries if entry is not None and entry.domain == DOMAIN
    ]
    if not switchbot_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_belonging",
            translation_placeholders={"device_id": device_id},
        )

    if not (
        loaded_entry := next(
            (
                entry
                for entry in switchbot_entries
                if entry.state is ConfigEntryState.LOADED
            ),
            None,
        )
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_entry_not_loaded",
            translation_placeholders={"device_id": device_id},
        )

    return loaded_entry


def _is_supported_keypad(entry: SwitchbotConfigEntry) -> bool:
    """Return if the entry is a supported keypad model."""
    allowed_sensor_types = {
        SupportedModels.KEYPAD_VISION.value,
        SupportedModels.KEYPAD_VISION_PRO.value,
    }
    return entry.data.get(CONF_SENSOR_TYPE) in allowed_sensor_types


@callback
def _async_target(
    hass: HomeAssistant, device_id: str
) -> SwitchbotDataUpdateCoordinator:
    """Return coordinator for a single target device."""
    entry = _async_get_switchbot_entry_for_device_id(hass, device_id)
    if not _is_supported_keypad(entry):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_keypad_vision_device",
        )

    return entry.runtime_data


async def async_add_password(call: ServiceCall) -> None:
    """Add a password to a SwitchBot keypad device."""
    password: str = call.data[ATTR_PASSWORD]
    device_id = call.data[ATTR_DEVICE_ID]

    coordinator = _async_target(call.hass, device_id)

    await coordinator.device.add_password(password)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the SwitchBot integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PASSWORD,
        async_add_password,
        schema=SCHEMA_ADD_PASSWORD_SERVICE,
    )
