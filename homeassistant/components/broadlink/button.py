"""Support for Broadlink buttons."""
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Platform
from .device import BroadlinkDevice, BroadlinkStores
from .entity import BroadlinkEntity
from .helpers import async_clean_registries


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink button."""
    device: BroadlinkDevice = hass.data[DOMAIN].devices[config_entry.entry_id]
    store = device.store
    assert store

    unique_ids: set[str] = set()
    entities: list[BroadlinkButton] = []
    for subdevice, commands in store.extract_devices_and_commands().items():
        for command in commands:
            unique_id = f"{device.unique_id}-codes-{subdevice}-{command}"
            unique_ids.add(unique_id)
            entities.append(
                BroadlinkButton(device, store, subdevice, command, unique_id)
            )

    async_add_entities(entities)

    async_clean_registries(hass, config_entry, unique_ids, Platform.BUTTON)


class BroadlinkButton(BroadlinkEntity, ButtonEntity):
    """Representation of a Broadlink button."""

    _device: BroadlinkDevice

    def __init__(
        self,
        device: BroadlinkDevice,
        store: BroadlinkStores,
        subdevice: str,
        command: str,
        unique_id: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(device)
        self._attr_name = f"{subdevice} {command}"
        self._attr_unique_id = unique_id
        self._subdevice = subdevice
        self._command = command
        self._store = store

    async def async_press(self, **kwargs: Any) -> None:
        """Trigger code by button press."""
        device = self._device
        store = self._store
        assert device.api
        code_list = store.extract_codes([self._command], self._subdevice)

        for code in store.toggled_codes(code_list, self._subdevice):
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
