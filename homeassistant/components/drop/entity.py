"""Base entity class for DROP entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import DROP_DeviceDataUpdateCoordinator


class DROP_Entity(Entity):
    """A base class for DROP entities."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entity_type: str, device: DROP_DeviceDataUpdateCoordinator, **kwargs
    ) -> None:
        """Init DROP entity."""
        self._attr_unique_id = f"{device.id}_{entity_type}"
        self._device: DROP_DeviceDataUpdateCoordinator = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.model,
            name=self._device.device_name,
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self.async_write_ha_state))
