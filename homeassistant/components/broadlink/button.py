"""Support for Broadlink buttons."""
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import BroadlinkDevice
from .entity import BroadlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink light."""
    device: BroadlinkDevice = hass.data[DOMAIN].devices[config_entry.entry_id]
    store = device.store

    entities = [
        BroadlinkButton(device, subdevice, command)
        for subdevice, commands in store.extract_devices_and_commands().items()
        for command in commands
    ]

    async_add_entities(entities)


class BroadlinkButton(BroadlinkEntity, ButtonEntity):
    """Representation of a Broadlink light."""

    _device: BroadlinkDevice

    def __init__(self, device: BroadlinkDevice, subdevice: str, command: str) -> None:
        """Initialize the light."""
        super().__init__(device)
        self._attr_name = f"{device.name} {subdevice} {command}"
        self._attr_unique_id = f"{device.unique_id}-codes-{subdevice}-{command}"
        self._subdevice = subdevice
        self._command = command

    async def async_press(self, **kwargs: Any) -> None:
        """Trigger code by button press."""
        device = self._device
        assert device.api
        code_list = device.store.extract_codes([self._command], self._subdevice)

        for code in device.store.toggled_codes(code_list, self._subdevice):
            await device.async_request(device.api.send_data, code)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device = self._device

        return DeviceInfo(
            identifiers={(DOMAIN, f"{device.unique_id}-codes-{self._subdevice}")},
            via_device=(DOMAIN, device.unique_id),
            name=self._subdevice,
        )
