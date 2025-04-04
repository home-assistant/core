"""Kuler Sky lights integration."""

import logging
from types import MappingProxyType

from homeassistant.components.bluetooth import DOMAIN as BLUETOOTH_DOMAIN
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.discovery_flow import DiscoveryKey

from .const import DOMAIN

PLATFORMS = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kuler Sky from a config entry."""
    ble_device = async_ble_device_from_address(
        hass, entry.data[CONF_ADDRESS], connectable=True
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # Version 1 was a single entry instance that started a bluetooth discovery
    # thread to add devices. Version 2 has one config entry per device, and
    # supports core bluetooth discovery
    if config_entry.version == 1:
        dev_reg = dr.async_get(hass)
        entity_reg = er.async_get(hass)
        devices = dev_reg.devices.get_devices_for_config_entry_id(config_entry.entry_id)

        if len(devices) == 0:
            _LOGGER.error("Unable to migrate; No devices registered")
            return False

        first_device = devices[0]
        address = next(iter(first_device.identifiers))[1]
        hass.config_entries.async_update_entry(
            config_entry,
            title=first_device.name or address,
            data={CONF_ADDRESS: address},
            discovery_keys=MappingProxyType(
                {
                    BLUETOOTH_DOMAIN: (
                        DiscoveryKey(
                            domain=BLUETOOTH_DOMAIN,
                            key=address,
                            version=1,
                        ),
                    )
                }
            ),
            unique_id=address,
            version=2,
        )

        # Create new config entries for the remaining devices
        for device in devices[1:]:
            address = next(iter(device.identifiers))[1]
            new_entry = ConfigEntry(
                data={CONF_ADDRESS: address},
                options=config_entry.options,
                discovery_keys=MappingProxyType(
                    {
                        BLUETOOTH_DOMAIN: (
                            DiscoveryKey(
                                domain=BLUETOOTH_DOMAIN,
                                key=address,
                                version=1,
                            ),
                        )
                    }
                ),
                domain=DOMAIN,
                source=config_entry.source,
                title=device.name or address,
                unique_id=address,
                subentries_data=None,
                version=2,
                minor_version=1,
            )
            await hass.config_entries.async_add(new_entry)

            entities = er.async_entries_for_device(
                entity_reg, device.id, include_disabled_entities=True
            )
            for entity in entities:
                entity_reg.async_update_entity(
                    entity.entity_id, config_entry_id=new_entry.entry_id
                )

            dev_reg.async_update_device(
                device.id,
                add_config_entry_id=new_entry.entry_id,
                remove_config_entry_id=config_entry.entry_id,
            )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
