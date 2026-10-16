"""The 1-Wire component."""

import logging

from aio_ownet.exceptions import OWServerError

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .onewirehub import OneWireConfigEntry, OneWireHub

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: OneWireConfigEntry) -> None:
    """Set up a 1-Wire proxy for a config entry."""
    onewire_hub = OneWireHub(hass, entry)
    try:
        await onewire_hub.initialize()
    except OWServerError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: str(entry.data[CONF_PORT]),
            },
        ) from exc

    entry.runtime_data = onewire_hub

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    onewire_hub.schedule_scan_for_new_devices()


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: OneWireConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    onewire_hub = config_entry.runtime_data
    device_ids = {
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    }
    if device_ids & onewire_hub.present_device_ids:
        return False
    for device_id in device_ids:
        onewire_hub.forget_device(device_id)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: OneWireConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, _PLATFORMS)
