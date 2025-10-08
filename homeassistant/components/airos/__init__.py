"""The Ubiquiti airOS integration."""

from __future__ import annotations

import logging

from airos.airos8 import AirOS8

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_PLATFORM
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, SECTION_ADVANCED_SETTINGS
from .coordinator import AirOSConfigEntry, AirOSDataUpdateCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Set up Ubiquiti airOS from a config entry."""

    # By default airOS 8 comes with self-signed SSL certificates,
    # with no option in the web UI to change or upload a custom certificate.
    session = async_get_clientsession(
        hass, verify_ssl=entry.data[SECTION_ADVANCED_SETTINGS][CONF_VERIFY_SSL]
    )

    airos_device = AirOS8(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
        use_ssl=entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL],
    )

    coordinator = AirOSDataUpdateCoordinator(hass, entry, airos_device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Migrate old config entry."""

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1 and entry.minor_version == 1:
        new_data = {**entry.data}
        advanced_data = {
            CONF_SSL: DEFAULT_SSL,
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        }
        new_data[SECTION_ADVANCED_SETTINGS] = advanced_data

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=2,
        )

    # As v6 has no device_id use mac_address in binary_sensor
    if entry.version == 1:
        device_registry = dr.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )

        if not device_entries:
            _LOGGER.debug("Nothing in device registry, assuming migration succeeded")
            hass.config_entries.async_update_entry(entry, minor_version=3)
            return True  # Nothing to migrate, complete version bump

        device_entry = device_entries[0]
        mac_address = None

        for connection_type, value in device_entry.connections:
            if connection_type == dr.CONNECTION_NETWORK_MAC:
                mac_address = dr.format_mac(value)
                break

        if not mac_address:
            _LOGGER.error(
                "No MAC address found for device %s, unable to migrate binary_sensors appropriately. Please remove and re-add the integration to avoid duplicate entities",
                device_entry.name,
            )
            return False

        @callback
        def update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
            """Update unique id from device_id to mac address."""
            if (euid := entry.unique_id) is not None:
                if (
                    entity_entry.platform == BINARY_SENSOR_PLATFORM
                    and entity_entry.unique_id.startswith(euid)
                ):
                    suffix = entity_entry.unique_id.removeprefix(euid)
                    new_unique_id = f"{mac_address}{suffix}"
                    _LOGGER.info(
                        "Migrating entity %s unique_id to %s",
                        entity_entry.entity_id,
                        new_unique_id,
                    )
                    return {"new_unique_id": new_unique_id}
            return None  # pragma: no cover

        await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)

        hass.config_entries.async_update_entry(entry, version=2, minor_version=3)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirOSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
