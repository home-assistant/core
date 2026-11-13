"""The lg_soundbar component."""

import logging

from homeassistant import core
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import test_connect
from .media_player import LGDevice, LGSoundbarConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: LGSoundbarConfigEntry
) -> None:
    """Set up platform from a ConfigEntry."""
    # Verify the device is reachable with the given
    # config before setting up the platform
    try:
        await hass.async_add_executor_job(
            test_connect, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except ConnectionError as err:
        raise ConfigEntryNotReady from err

    device = LGDevice(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.unique_id or entry.entry_id,
    )
    try:
        await hass.async_add_executor_job(device.connect)
    except OSError as err:
        raise ConfigEntryNotReady from err

    async def _close_device() -> None:
        await hass.async_add_executor_job(device.close)

    entry.async_on_unload(_close_device)
    entry.runtime_data = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: LGSoundbarConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
