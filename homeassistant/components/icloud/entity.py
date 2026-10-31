"""Base entity for the iCloud integration."""

from typing import override

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .account import IcloudAccount, IcloudDevice
from .const import DOMAIN


class IcloudDeviceEntity(Entity):
    """Base class for an entity backed by an iCloud device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, account: IcloudAccount, device: IcloudDevice) -> None:
        """Initialize the entity."""
        self._account = account
        self._device = device
        self._unsub_dispatcher: CALLBACK_TYPE | None = None
        self._attr_device_info = DeviceInfo(
            configuration_url="https://icloud.com/",
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer="Apple",
            model=device.device_model,
            name=device.name,
        )

    @callback
    def _async_device_updated(self) -> None:
        """Write state when the device is updated."""
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._account.signal_device_update, self._async_device_updated
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
