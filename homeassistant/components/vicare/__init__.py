"""The ViCare integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
import logging
import os
from typing import Any

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device
from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_HEATING_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEATING_TYPE_TO_CREATOR_METHOD,
    PLATFORMS,
    VICARE_API,
    VICARE_DEVICE_CONFIG,
    VICARE_DEVICE_CONFIG_LIST,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)
_TOKEN_FILENAME = "vicare_token.save"


@dataclass(frozen=True)
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[Device], Any]


@dataclass(frozen=True)
class ViCareRequiredKeysMixinWithSet(ViCareRequiredKeysMixin):
    """Mixin for required keys with setter."""

    value_setter: Callable[[Device], bool]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    try:
        await hass.async_add_executor_job(setup_vicare_api, hass, entry)
    except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError) as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err

    await async_migrate_devices(hass, entry)
    await async_migrate_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def vicare_login(hass: HomeAssistant, entry_data: Mapping[str, Any]) -> PyViCare:
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(DEFAULT_SCAN_INTERVAL)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, _TOKEN_FILENAME),
    )
    return vicare_api


def setup_vicare_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up PyVicare API."""
    vicare_api = vicare_login(hass, entry.data)

    for device in vicare_api.devices:
        _LOGGER.info(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    # Currently we only support a single device
    device_list = vicare_api.devices
    device = device_list[0]
    hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG_LIST] = device_list
    hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG] = device
    hass.data[DOMAIN][entry.entry_id][VICARE_API] = getattr(
        device,
        HEATING_TYPE_TO_CREATOR_METHOD[HeatingType(entry.data[CONF_HEATING_TYPE])],
    )()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    with suppress(FileNotFoundError):
        await hass.async_add_executor_job(
            os.remove, hass.config.path(STORAGE_DIR, _TOKEN_FILENAME)
        )

    return unload_ok


async def async_migrate_devices(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Migrate old entry."""
    registry = dr.async_get(hass)

    device_config = hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]
    device = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]
    old_serial: str = device_config.getConfig().serial
    new_serial: str = device.getSerial()

    if new_serial == old_serial:
        return

    # Migrate devices
    for device_entry in dr.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        if device_entry.serial_number == old_serial:
            _LOGGER.debug(
                "Migrating device %s serial to %s", device_entry.name, new_serial
            )
            registry.async_update_device(
                device_entry.id,
                serial_number=new_serial,
                new_identifiers={(DOMAIN, new_serial)},
            )


async def async_migrate_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Migrate old entry."""
    device_config = hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]
    device = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]
    old_serial: str = device_config.getConfig().serial
    new_serial: str = device.getSerial()

    @callback
    def _update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if entity_entry.unique_id.startswith(new_serial):
            # Already correct, nothing to do
            return None

        unique_id_parts = entity_entry.unique_id.split("-")
        unique_id_parts[0] = new_serial
        entity_new_unique_id = "-".join(unique_id_parts)

        _LOGGER.debug(
            "Migrating entity %s from %s to new id %s",
            entity_entry.entity_id,
            entity_entry.unique_id,
            entity_new_unique_id,
        )
        return {"new_unique_id": entity_new_unique_id}

    if new_serial == old_serial:
        return

    # Migrate entities
    await er.async_migrate_entries(hass, config_entry.entry_id, _update_unique_id)
