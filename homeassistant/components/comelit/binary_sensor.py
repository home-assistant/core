"""Support for sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aiocomelit.api import ComelitVedoZoneObject
from aiocomelit.const import ALARM_ZONE, AlarmZoneState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ObjectClassType
from .coordinator import ComelitConfigEntry, ComelitSerialBridge, ComelitVedoSystem
from .utils import new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit VEDO presence sensors."""

    coordinator = config_entry.runtime_data
    is_bridge = isinstance(coordinator, ComelitSerialBridge)

    if TYPE_CHECKING:
        if is_bridge:
            assert isinstance(coordinator, ComelitSerialBridge)
        else:
            assert isinstance(coordinator, ComelitVedoSystem)

    def _add_new_entities(new_devices: list[ObjectClassType], dev_type: str) -> None:
        """Add entities for new monitors."""
        entities = [
            ComelitVedoBinarySensorEntity(coordinator, device, config_entry.entry_id)
            for device in coordinator.data[dev_type].values()
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        new_device_listener(coordinator, _add_new_entities, ALARM_ZONE)
    )


class ComelitVedoBinarySensorEntity(
    CoordinatorEntity[ComelitVedoSystem | ComelitSerialBridge], BinarySensorEntity
):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: ComelitVedoSystem | ComelitSerialBridge,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init sensor entity."""
        self._zone_index = zone.index
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-presence-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone, "zone")

    @property
    def _zone(self) -> ComelitVedoZoneObject:
        """Return zone object."""
        return cast(
            ComelitVedoZoneObject, self.coordinator.data[ALARM_ZONE][self._zone_index]
        )

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if self._zone.human_status in [
            AlarmZoneState.FAULTY,
            AlarmZoneState.UNAVAILABLE,
            AlarmZoneState.UNKNOWN,
        ]:
            return False
        return super().available

    @property
    def is_on(self) -> bool:
        """Presence detected."""
        return self._zone.status_api == "0001"
