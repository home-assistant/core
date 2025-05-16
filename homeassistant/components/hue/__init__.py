"""Support for the Philips Hue system."""

from aiohue.util import normalize_bridge_id

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .bridge import HueBridge, HueConfigEntry
from .const import DOMAIN, SERVICE_HUE_ACTIVATE_SCENE
from .migration import check_migration
from .services import async_register_services


async def async_setup_entry(hass: HomeAssistant, entry: HueConfigEntry) -> bool:
    """Set up a bridge from a config entry."""
    # check (and run) migrations if needed
    await check_migration(hass, entry)

    # setup the bridge instance
    bridge = HueBridge(hass, entry)
    if not await bridge.async_initialize_bridge():
        return False

    # register Hue domain services
    async_register_services(hass)

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
            # There is another entry but it is ignored, delete that one and update this one
            hass.async_create_task(
                hass.config_entries.async_remove(other_entry.entry_id)
            )
            hass.config_entries.async_update_entry(entry, unique_id=unique_id)
        else:
            # There is another entry that already has the right unique ID. Delete this entry
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return False

    # add bridge device to device registry
    device_registry = dr.async_get(hass)
    if bridge.api_version == 1:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, api.config.mac_address)},
            identifiers={(DOMAIN, api.config.bridge_id)},
            manufacturer="Signify",
            name=api.config.name,
            model=api.config.model_id,
            sw_version=api.config.software_version,
        )
        # create persistent notification if we found a bridge version with security vulnerability
        if (
            api.config.model_id == "BSB002"
            and api.config.software_version < "1935144040"
        ):
            persistent_notification.async_create(
                hass,
                (
                    "Your Hue hub has a known security vulnerability ([CVE-2020-6007] "
                    "(https://cve.circl.lu/cve/CVE-2020-6007)). "
                    "Go to the Hue app and check for software updates."
                ),
                "Signify Hue",
                "hue_hub_firmware",
            )
    else:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, api.config.mac_address)},
            identifiers={
                (DOMAIN, api.config.bridge_id),
                (DOMAIN, api.config.bridge_device.id),
            },
            manufacturer=api.config.bridge_device.product_data.manufacturer_name,
            name=api.config.name,
            model=api.config.model_id,
            sw_version=api.config.software_version,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HueConfigEntry) -> bool:
    """Unload a config entry."""
    unload_success = await entry.runtime_data.async_reset()
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_HUE_ACTIVATE_SCENE)
    return unload_success
