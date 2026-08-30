"""Support for the Philips Hue system."""

from aiohue.util import normalize_bridge_id

from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .bridge import HueBridge, HueConfigEntry, _async_register_bridge_device
from .const import DOMAIN
from .migration import check_migration
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hue integration."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HueConfigEntry) -> bool:
    """Set up a bridge from a config entry."""
    # check (and run) migrations if needed
    await check_migration(hass, entry)

    # setup the bridge instance
    bridge = HueBridge(hass, entry)
    if not await bridge.async_initialize_bridge():
        return False

    api = bridge.api

    # For backwards compat
    unique_id = normalize_bridge_id(api.config.bridge_id)
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=unique_id)

    # For recovering from bug where we incorrectly assumed homekit ID = bridge ID
    # Remove this logic after Home Assistant 2022.4
    elif entry.unique_id != unique_id:
        # Find entries with this unique ID
        other_entry = next(
            (
                entry
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id == unique_id
            ),
            None,
        )
        if other_entry is None:
            # If no other entry, update unique ID of this entry ID.
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)

        elif other_entry.source == SOURCE_IGNORE:
            # There is another entry but it is ignored, delete that
            # one and update this one
            hass.async_create_task(
                hass.config_entries.async_remove(other_entry.entry_id)
            )
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)
        else:
            # There is another entry that already has the right unique
            # ID. Delete this entry
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False

    # v1 bridges already register their device before platform forwarding, so
    # light/sensor entities can resolve it as their via_device parent; only
    # register it here if that has not already happened. v2 bridges are always
    # (re)registered here to merge the network MAC connection into the bridge
    # device created by async_setup_devices with only its Zigbee MAC.
    if bridge.api_version != 1 or (
        dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, api.config.bridge_id), entry.entry_id
        )
        is None
    ):
        _async_register_bridge_device(hass, entry, api, bridge.api_version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HueConfigEntry) -> bool:
    """Unload a config entry."""
    return await entry.runtime_data.async_reset()
