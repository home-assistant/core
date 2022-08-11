"""The pjlink component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import _LOGGER


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        config_entry.version = 2
        unique_id = config_entry.entry_id

        if unique_id is None:
            # How to generate a unique ID?
            # The PJLink API does not expose MAC address or serial number, only name, manufacturer, and model
            # Can we get the MAC address from the IP address?

            unique_id = config_entry.entry_id
            _LOGGER.debug("===== setting pjlink unique_id: %s ", unique_id)

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data, "unique_id": unique_id}
        )
        _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the config entry."""

    _LOGGER.warning("==> Running async_setup_entry from pjlink__init__")

    await hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            config_entry, Platform.MEDIA_PLAYER
        )
    )

    # This seems to fail now with OperationNotAllowed
    # https://developers.home-assistant.io/blog/2022/06/13/unsafe_reloads_during_entry_setup
    # await hass.config_entries.async_reload(config_entry.entry_id)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    # Do we need to do anything here? Do we even need this method?
    return True
