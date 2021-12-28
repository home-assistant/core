"""The SenseME integration."""
import asyncio
import logging

from aiosenseme import (
    SensemeDevice,
    __version__ as aiosenseme_version,
    async_get_device_by_device_info,
)

from homeassistant.components.binary_sensor import DOMAIN as BINARYSENSOR_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_INFO, DOMAIN, UPDATE_RATE

PLATFORMS = [FAN_DOMAIN, BINARYSENSOR_DOMAIN, LIGHT_DOMAIN, SWITCH_DOMAIN]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the SenseME component."""
    _LOGGER.debug("Using aiosenseme library version %s", aiosenseme_version)
    hass.data[DOMAIN] = {}
    if config.get(DOMAIN) is not None:
        _LOGGER.error(
            "Configuration of senseme integration via yaml is deprecated, "
            "instead use Home Assistant frontend to add this integration"
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up SenseME from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = {}

    status, device = await async_get_device_by_device_info(
        info=entry.data[CONF_INFO], start_first=True, refresh_minutes=UPDATE_RATE
    )

    if not status:
        # even if the device could not connect it will keep trying because start_first=True
        device.stop()
        _LOGGER.warning(
            "%s: Connect to address %s failed",
            device.name,
            device.address,
        )
        raise ConfigEntryNotReady

    await device.async_update(not status)

    hass.data[DOMAIN][entry.entry_id][CONF_DEVICE] = device

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN][entry.entry_id][CONF_DEVICE].stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SensemeEntity:
    """Base class for senseme entities."""

    def __init__(self, device: SensemeDevice, name: str):
        """Initialize the entity."""
        self._device = device
        self._name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Get device info for Home Assistant."""
        return {
            "connections": {("mac", self._device.mac)},
            "identifiers": {("uuid", self._device.uuid)},
            "name": self._device.name,
            "manufacturer": "Big Ass Fans",
            "model": self._device.model,
            "sw_version": self._device.fw_version,
            "suggested_area": self._device.room_name,
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Get the current device state attributes."""
        return {
            "room_name": self._device.room_name,
            "room_type": self._device.room_type,
        }

    @property
    def available(self) -> bool:
        """Return True if available/operational."""
        return self._device.available

    @property
    def should_poll(self) -> bool:
        """State is pushed."""
        return False

    @property
    def name(self) -> str:
        """Get name."""
        return self._name

    async def async_added_to_hass(self):
        """Add data updated listener after this object has been initialized."""
        self._device.add_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Remove data updated listener after this object has been initialized."""
        self._device.remove_callback(self.async_write_ha_state)
