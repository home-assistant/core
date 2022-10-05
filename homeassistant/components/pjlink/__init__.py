"""The pjlink component."""

import socket

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENCODING, CONFIG_ENTRY_SCHEMA, DEFAULT_TIMEOUT, DOMAIN
from .coordinator import PJLinkUpdateCoordinator
from .device import PJLinkDevice

PLATFORM_SCHEMA = CONFIG_ENTRY_SCHEMA

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

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    name = entry.data[CONF_NAME]
    encoding = entry.data[CONF_ENCODING]
    password = entry.data[CONF_PASSWORD]
    timeout = DEFAULT_TIMEOUT

    unique_id = entry.unique_id

    if unique_id is None:
        # Create a unique ID
        unique_id = entry.entry_id

        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "unique_id": unique_id}
        )

    device = PJLinkDevice(host, port, name, encoding, password, timeout)

    coordinator = PJLinkUpdateCoordinator(hass, device, unique_id)

    try:
        await coordinator.async_config_entry_first_refresh()
    except socket.timeout as exc:
        device.async_stop()
        raise ConfigEntryNotReady() from exc
    except ConfigEntryNotReady:
        device.async_stop()
        raise

    domain_data[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Destroy a PJLink device."""
    domain_data = hass.data[DOMAIN]

    domain_data.pop(entry.entry_id)

    return True
