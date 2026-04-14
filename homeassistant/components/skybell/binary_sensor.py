"""Binary sensor support for the Skybell HD Doorbell."""

from __future__ import annotations

from aioskybell.helpers import const as CONST

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkybellConfigEntry, SkybellDataUpdateCoordinator
from .entity import SkybellEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="button",
        translation_key="button",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkybellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Skybell binary sensor."""
    async_add_entities(
        SkybellBinarySensor(coordinator, sensor)
        for sensor in BINARY_SENSOR_TYPES
        for coordinator in entry.runtime_data
    )


class SkybellBinarySensor(SkybellEntity, BinarySensorEntity):
    """A binary sensor implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor for a Skybell device."""
        super().__init__(coordinator, description)
        self._event: dict[str, str] = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        event = self._device.latest(self.entity_description.key)
        self._attr_is_on = bool(event.get(CONST.ID) != self._event.get(CONST.ID))
        self._event = event
        super()._handle_coordinator_update()
