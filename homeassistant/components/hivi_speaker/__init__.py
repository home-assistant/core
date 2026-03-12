import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .device import HIVIDevice
from .device_manager import HIVIDeviceManager
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up the config entry"""

    # Create device manager
    device_manager = HIVIDeviceManager(hass, config_entry)
    await device_manager.async_setup()

    # Store to hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    hass.data[DOMAIN][config_entry.entry_id]["device_manager"] = device_manager

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(
        config_entry, ["media_player", "switch"]
    )

    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload config entry and clean up related resources"""
    _LOGGER.debug("Starting to unload config entry %s", entry.entry_id)

    # Get stored data (may have been partially cleaned up)
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    # 1) Clean up device manager (cancel background tasks, etc.)
    device_manager = data.get("device_manager")
    if device_manager:
        try:
            await device_manager.async_cleanup()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Exception occurred while cleaning up device_manager")

    # 2) Standard platform unloading
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, ["media_player", "switch"]
        )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to call async_unload_platforms")
        unload_ok = False

    # 3) Clean up this extension's entry from hass.data
    # Note: Do not remove devices from the device registry here. Unload (e.g. on
    # reload) should not delete devices; removal is handled by
    # async_remove_config_entry_device or when the config entry is removed.
    try:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN, None)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Exception occurred while cleaning up hass.data")

    if not unload_ok:
        _LOGGER.error(
            "Platform unloading partially failed (unload_ok=False), there may be residual entities or platforms"
        )
    else:
        _LOGGER.debug("Config entry %s unloaded successfully", entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Called when the config entry is actually removed (not just unloaded).

    Clean up devices from the device registry and any persistent storage,
    since follower speakers disappear from the network and cached data
    should not survive a full removal.
    """
    _LOGGER.debug("Removing config entry %s – cleaning up devices", entry.entry_id)

    try:
        dev_reg = dr.async_get(hass)
        for device in list(dev_reg.devices.values()):
            config_entries = getattr(device, "config_entries", None)
            if config_entries and entry.entry_id in config_entries:
                dev_reg.async_remove_device(device.id)
            elif getattr(device, "config_entry_id", None) == entry.entry_id:
                dev_reg.async_remove_device(device.id)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error cleaning up device registry on entry removal")

    try:
        store = Store(hass, 1, "hivi_speaker_device_data")
        await store.async_save({"device_data": {}, "version": 1})
        _LOGGER.debug("Persistent device data storage cleared")
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error clearing persistent storage on entry removal")


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Handle removal of a device from the UI/device registry.

    Return True to allow Home Assistant to remove the device entry.
    Only devices belonging to this integration (DOMAIN in identifiers) are cleaned up.
    """
    # Only handle devices that belong to this integration
    if not any(identifier[0] == DOMAIN for identifier in device_entry.identifiers):
        return False

    try:
        domain_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
        device_manager = domain_data.get("device_manager")
        if device_manager is None:
            _LOGGER.debug(
                "Device manager not found for entry %s, allowing device deletion %s",
                config_entry.entry_id,
                device_entry.id,
            )
            return True

        ha_device_id = device_entry.id
        speaker_device_id = None
        device_dict = (
            device_manager.device_data_registry.get_device_dict_by_ha_device_id(
                ha_device_id, default=None
            )
        )
        if device_dict is not None:
            device_obj = HIVIDevice(**device_dict)
            speaker_device_id = device_obj.speaker_device_id

        await device_manager.async_remove_device_with_entities(ha_device_id)
        _LOGGER.debug(
            "Requested device manager to delete device %s and its entities",
            ha_device_id,
        )

        if speaker_device_id:
            await device_manager.remove_control_entities_by_speaker_device_id(
                speaker_device_id
            )
            _LOGGER.debug(
                "Requested device manager to delete control entities for speaker device ID %s",
                speaker_device_id,
            )

        return True

    except Exception as exc:
        _LOGGER.exception(
            "Error in async_remove_config_entry_device for device %s: %s",
            device_entry.id,
            exc,
        )
        return True
