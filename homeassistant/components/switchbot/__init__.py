"""Support for Switchbot devices."""

from collections.abc import Mapping
import logging
from typing import Any

import switchbot

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    ATTR_BOT,
    ATTR_CURTAIN,
    ATTR_HYGROMETER,
    CONF_RETRY_COUNT,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
)
from .coordinator import SwitchbotDataUpdateCoordinator

PLATFORMS_BY_TYPE = {
    ATTR_BOT: [Platform.SWITCH, Platform.SENSOR],
    ATTR_CURTAIN: [Platform.COVER, Platform.BINARY_SENSOR, Platform.SENSOR],
    ATTR_HYGROMETER: [Platform.SENSOR],
}
CLASS_BY_DEVICE = {
    ATTR_CURTAIN: switchbot.SwitchbotCurtain,
    ATTR_BOT: switchbot.Switchbot,
}

_LOGGER = logging.getLogger(__name__)


class OptionsListener:
    """Listen for changes in options."""

    def __init__(self, original_options: Mapping[str, Any]) -> None:
        """Initialize the options listener."""
        self._original_options = dict(original_options)

    async def async_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        if dict(entry.options) != self._original_options:
            await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switchbot from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if CONF_ADDRESS not in entry.data and CONF_MAC in entry.data:
        # Bleak uses addresses not mac addresses which are are actually
        # UUIDs on some platforms (MacOS).
        mac = entry.data[CONF_MAC]
        if "-" not in mac:
            mac = dr.format_mac(mac)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ADDRESS: mac},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
        )

    sensor_type: str = entry.data[CONF_SENSOR_TYPE]
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper())
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Switchbot {sensor_type} with address {address}"
        )
    cls = CLASS_BY_DEVICE.get(sensor_type, switchbot.SwitchbotDevice)
    device = cls(
        device=ble_device,
        password=entry.data.get(CONF_PASSWORD),
        retry_count=entry.options[CONF_RETRY_COUNT],
    )
    coordinator = hass.data[DOMAIN][entry.entry_id] = SwitchbotDataUpdateCoordinator(
        hass, _LOGGER, ble_device, device
    )
    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(f"Switchbot {sensor_type} with {address} not ready")

    # Holding a reference here since add_update_listener
    # holds a weak reference to the callback.
    options_listener = OptionsListener(entry.options)

    entry.async_on_unload(
        entry.add_update_listener(options_listener.async_update_listener)
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_SENSOR_TYPE]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.config_entries.async_entries(DOMAIN):
            hass.data.pop(DOMAIN)

    return unload_ok
