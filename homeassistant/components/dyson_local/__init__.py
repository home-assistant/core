"""Support for Dyson devices."""
from __future__ import annotations

from libdyson import MessageType, get_device
from libdyson.dyson_device import DysonDevice
from libdyson.exceptions import DysonException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_CREDENTIAL, CONF_DEVICE_TYPE, CONF_SERIAL, DATA_DEVICES, DOMAIN

_PLATFORMS = ["binary_sensor", "sensor", "vacuum"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Dyson integration."""
    hass.data[DOMAIN] = {
        DATA_DEVICES: {},
    }
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dyson from a config entry."""
    device = get_device(
        entry.data[CONF_SERIAL],
        entry.data[CONF_CREDENTIAL],
        entry.data[CONF_DEVICE_TYPE],
    )

    try:
        await hass.async_add_executor_job(device.connect, entry.data[CONF_HOST])
    except DysonException as err:
        raise ConfigEntryNotReady from err
    hass.data[DOMAIN][DATA_DEVICES][entry.entry_id] = device
    for component in _PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dyson local."""
    device = hass.data[DOMAIN][DATA_DEVICES][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_DEVICES].pop(entry.entry_id)
        await hass.async_add_executor_job(device.disconnect)
    return unload_ok


class DysonEntity(Entity):
    """Dyson entity base class."""

    _MESSAGE_TYPE = MessageType.STATE

    def __init__(self, device: DysonDevice, name: str) -> None:
        """Initialize the entity."""
        self._device = device
        self._name = name

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._device.add_message_listener(self._on_message)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity to be removed from hass."""
        self._device.remove_message_listener(self._on_message)

    def _on_message(self, message_type: MessageType) -> None:
        if self._MESSAGE_TYPE is None or message_type == self._MESSAGE_TYPE:
            self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if self.sub_name is None:
            return self._name
        return f"{self._name} {self.sub_name}"

    @property
    def sub_name(self) -> str | None:
        """Return sub name of the entity."""
        return None

    @property
    def unique_id(self) -> str:
        """Return the entity unique id."""
        if self.sub_unique_id is None:
            return self._device.serial
        return f"{self._device.serial}-{self.sub_unique_id}"

    @property
    def sub_unique_id(self) -> str | None:
        """Return the entity sub unique id."""
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info of the entity."""
        return {
            "identifiers": {(DOMAIN, self._device.serial)},
            "name": self._name,
            "manufacturer": "Dyson",
            "model": self._device.device_type,
        }
