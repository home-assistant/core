"""The ViCare integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from PyViCare.PyViCare import PyViCare
from PyViCare.PyViCareDevice import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import STORAGE_DIR

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS, VICARE_DEVICE_CONFIG
from .helpers import get_unique_device_id

_LOGGER = logging.getLogger(__name__)


@dataclass()
class ViCareRequiredKeysMixin:
    """Mixin for required keys."""

    value_getter: Callable[[Device], bool]


@dataclass()
class ViCareRequiredKeysMixinWithSet:
    """Mixin for required keys with setter."""

    value_getter: Callable[[Device], bool]
    value_setter: Callable[[Device], bool]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    entity_registry = er.async_get(hass)

    if config_entry.version == 1:
        devices = hass.data[DOMAIN][config_entry.entry_id][VICARE_DEVICE_CONFIG]
        if devices is None or len(devices) == 0:
            return True

        @callback
        def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
            new_unique_id = entry.unique_id.replace(
                f"{devices[0].getConfig().serial}-",
                f"{get_unique_device_id(devices[0])}-",
            )
            _LOGGER.debug(
                "Migrating entity '%s' unique_id from '%s' to '%s'",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
            )
            if existing_entity_id := entity_registry.async_get_entity_id(
                entry.domain, entry.platform, new_unique_id
            ):
                _LOGGER.warning(
                    "Cannot migrate to unique_id '%s', already exists for '%s'",
                    new_unique_id,
                    existing_entity_id,
                )
                return None
            return {
                "new_unique_id": new_unique_id,
            }

        await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
        config_entry.version = 2

        return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from config entry."""
    _LOGGER.debug("Setting up ViCare component")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.async_add_executor_job(setup_vicare_api, hass, entry)

    await _async_migrate_entries(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def vicare_login(hass, entry_data):
    """Login via PyVicare API."""
    vicare_api = PyViCare()
    vicare_api.setCacheDuration(DEFAULT_SCAN_INTERVAL)
    vicare_api.initWithCredentials(
        entry_data[CONF_USERNAME],
        entry_data[CONF_PASSWORD],
        entry_data[CONF_CLIENT_ID],
        hass.config.path(STORAGE_DIR, "vicare_token.save"),
    )
    return vicare_api


def setup_vicare_api(hass, entry):
    """Set up PyVicare API."""
    vicare_api = vicare_login(hass, entry.data)

    for device in vicare_api.devices:
        _LOGGER.info(
            "Found device: %s (online: %s)", device.getModel(), str(device.isOnline())
        )

    # Readjust scan interval: each device has its own API endpoint
    vicare_api.setCacheDuration(DEFAULT_SCAN_INTERVAL * len(vicare_api.devices))

    hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG] = vicare_api.devices


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ViCare config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
