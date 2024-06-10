"""Cover Entity for Genie Garage Door."""

from typing import Any

from genie_partner_sdk.model import GarageDoor

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AladdinConnectConfigEntry, AladdinConnectCoordinator
from .entity import AladdinConnectEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AladdinConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aladdin Connect platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(AladdinDevice(coordinator, door) for door in coordinator.doors)


class AladdinDevice(AladdinConnectEntity, CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self, coordinator: AladdinConnectCoordinator, device: GarageDoor
    ) -> None:
        """Initialize the Aladdin Connect cover."""
        super().__init__(coordinator, device)
        self._attr_unique_id = device.unique_id

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        await self.coordinator.acc.open_door(
            self._device.device_id, self._device.door_number
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        await self.coordinator.acc.close_door(
            self._device.device_id, self._device.door_number
        )

    @property
    def is_closed(self) -> bool | None:
        """Update is closed attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "closed")

    @property
    def is_closing(self) -> bool | None:
        """Update is closing attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "closing")

    @property
    def is_opening(self) -> bool | None:
        """Update is opening attribute."""
        value = self.coordinator.acc.get_door_status(
            self._device.device_id, self._device.door_number
        )
        if value is None:
            return None
        return bool(value == "opening")
