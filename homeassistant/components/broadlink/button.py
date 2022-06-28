"""Support for Broadlink buttons."""
from typing import Any

from broadlink.exceptions import BroadlinkException

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_STORES_CHANGED, Platform
from .device import BroadlinkDevice, BroadlinkStores, BroadlinkStoresChanges
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
    entity_registry = er.async_get(hass)

    def _get_unique_id(subdevice: str, command: str):
        return f"{device.unique_id}-codes-{subdevice}-{command}"

    unique_ids: set[str] = set()
    entities: list[BroadlinkButton] = []
    for subdevice, commands in store.extract_devices_and_commands().items():
        for command in commands:
            unique_id = _get_unique_id(subdevice, command)
            unique_ids.add(unique_id)
            entities.append(
                BroadlinkButton(device, store, subdevice, command, unique_id)
            )

    async_add_entities(entities)

    async_clean_registries(hass, config_entry, unique_ids, Platform.BUTTON)

    @callback
    def _stores_changed(data: BroadlinkStoresChanges):
        subdevice = data.subdevice
        assert store

        for command in data.added:
            unique_id = _get_unique_id(subdevice, command)
            async_add_entities(
                [BroadlinkButton(device, store, subdevice, command, unique_id)]
            )

        for command in data.removed:
            unique_id = _get_unique_id(subdevice, command)
            entity_id = entity_registry.async_get_entity_id(
                Platform.BUTTON, DOMAIN, unique_id
            )
            assert entity_id
            entity_registry.async_remove(entity_id)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_STORES_CHANGED.format(config_entry.unique_id), _stores_changed
        )
    )


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
            try:
                await device.async_request(device.api.send_data, code)
            except (BroadlinkException, OSError) as err:
                raise HomeAssistantError(
                    f"Error communicating with device: {repr(err)} when pressing '{self.entity_id}'"
                ) from err

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device = self._device

        return DeviceInfo(
            identifiers={(DOMAIN, f"{device.unique_id}-codes-{self._subdevice}")},
            via_device=(DOMAIN, device.unique_id),
            name=self._subdevice,
        )
