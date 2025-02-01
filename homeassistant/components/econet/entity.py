"""Support for EcoNet products."""

from pyeconet.equipment import Equipment

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PUSH_UPDATE


class EcoNetEntity[_EquipmentT: Equipment = Equipment](Entity):
    """Define a base EcoNet entity."""

    _attr_should_poll = False

    def __init__(self, econet: _EquipmentT) -> None:
        """Initialize."""
        self._econet = econet
        self._attr_name = econet.device_name
        self._attr_unique_id = f"{econet.device_id}_{econet.device_name}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, PUSH_UPDATE, self.on_update_received)
        )

    @callback
    def on_update_received(self) -> None:
        """Update was pushed from the ecoent API."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the device is online or not."""
        return self._econet.connected

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._econet.device_id)},
            manufacturer="Rheem",
            name=self._econet.device_name,
        )
