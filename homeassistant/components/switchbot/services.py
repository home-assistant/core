"""Services for the SwitchBot integration."""

from __future__ import annotations

import asyncio
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.target import TargetSelection

from .const import DOMAIN, SupportedModels
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator

SERVICE_ADD_PASSWORD = "add_password"

ATTR_PASSWORD = "password"

_PASSWORD_VALIDATOR = vol.All(cv.string, cv.matches_regex(r"^\d{6,12}$"))

SCHEMA_ADD_PASSWORD_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_PASSWORD): _PASSWORD_VALIDATOR,
        **cv.TARGET_SERVICE_FIELDS,
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_GET_PASSWORD_COUNT_SERVICE = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
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

    if not device_entry.config_entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_without_config_entry",
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

    return cast(SwitchbotConfigEntry, loaded_entry)


def _is_supported_keypad(entry: SwitchbotConfigEntry) -> bool:
    """Return if the entry is a supported keypad model."""
    allowed_sensor_types = {
        SupportedModels.KEYPAD_VISION.value,
        SupportedModels.KEYPAD_VISION_PRO.value,
    }
    return entry.data.get(CONF_SENSOR_TYPE) in allowed_sensor_types


@callback
def _async_extract_target_device_ids(call: ServiceCall) -> set[str]:
    """Extract device ids from a service call target."""
    selection = TargetSelection(call.data)
    device_ids = set(selection.device_ids)
    if not device_ids:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_device_id",
        )
    return device_ids


@callback
def _async_targets(
    hass: HomeAssistant, device_ids: set[str]
) -> tuple[dict[str, SwitchbotDataUpdateCoordinator], dict[str, set[str]]]:
    """Group targets by config entry id."""
    coordinators_by_entry_id: dict[str, SwitchbotDataUpdateCoordinator] = {}
    device_ids_by_entry_id: dict[str, set[str]] = {}

    for device_id in device_ids:
        entry = _async_get_switchbot_entry_for_device_id(hass, device_id)
        if not _is_supported_keypad(entry):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_keypad_vision_device",
            )

        coordinators_by_entry_id.setdefault(entry.entry_id, entry.runtime_data)
        device_ids_by_entry_id.setdefault(entry.entry_id, set()).add(device_id)

    return coordinators_by_entry_id, device_ids_by_entry_id


async def async_add_password(call: ServiceCall) -> None:
    """Add a password to a SwitchBot keypad device."""
    password: str = call.data[ATTR_PASSWORD]
    device_ids = _async_extract_target_device_ids(call)

    coordinators_by_entry_id, _ = _async_targets(call.hass, device_ids)

    await asyncio.gather(
        *(
            coordinator.device.add_password(password)
            for coordinator in coordinators_by_entry_id.values()
        )
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the SwitchBot integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PASSWORD,
        async_add_password,
        schema=SCHEMA_ADD_PASSWORD_SERVICE,
    )
