"""Support for Broadlink buttons."""
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get as async_get_registry,
)

from .const import DOMAIN, Platform
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
    entity_registry = async_get_registry(hass)

    entity_ids = {
        entry.unique_id: entry.entity_id
        for entry in async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == Platform.BUTTON
    }

    entities: list[BroadlinkButton] = []
    for subdevice, commands in store.extract_devices_and_commands().items():
        for command in commands:
            unique_id = f"{device.unique_id}-codes-{subdevice}-{command}"
            entities.append(BroadlinkButton(device, subdevice, command, unique_id))
            entity_ids.pop(unique_id, None)

    async_add_entities(entities)

    for entity_id in entity_ids.values():
        entity_registry.async_remove(entity_id)


class BroadlinkButton(BroadlinkEntity, ButtonEntity):
    """Representation of a Broadlink light."""

    _device: BroadlinkDevice

    def __init__(
        self, device: BroadlinkDevice, subdevice: str, command: str, unique_id: str
    ) -> None:
        """Initialize the light."""
        super().__init__(device)
        self._attr_name = f"{subdevice} {command}"
        self._attr_unique_id = unique_id
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
