"""The pjlink component."""

import asyncio
import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PJLinkUpdateCoordinator
from .device import PJLinkDevice
from .util import PJLinkConfig

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up a PJLink device from a yaml entry (deprecated)."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a PJLink device from a UI config entry."""
    domain_data = hass.data[DOMAIN]

    if entry.entry_id in domain_data:
        return True

    conf = PJLinkConfig.from_dict(dict(entry.data))

    unique_id = entry.unique_id

    if unique_id is None:
        # Create a unique ID
        unique_id = entry.entry_id

        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "unique_id": unique_id}
        )

    device = PJLinkDevice(conf)

    coordinator = PJLinkUpdateCoordinator(hass, device, unique_id)

    try:
        await coordinator.async_config_entry_first_refresh()
    except socket.timeout as exc:
        device.async_stop()
        raise ConfigEntryNotReady() from exc
    except AssertionError as exc:
        device.async_stop()
        raise ConfigEntryNotReady() from exc
    except ConfigEntryNotReady:
        device.async_stop()
        raise

    domain_data[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    remove_update_listener = entry.add_update_listener(update_listener)

    entry.async_on_unload(remove_update_listener)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Destroy a PJLink device."""
    domain_data = hass.data[DOMAIN]

    if entry.entry_id in domain_data:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )

        domain_data[entry.entry_id].device.async_stop()

        domain_data.pop(entry.entry_id)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
