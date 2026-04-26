"""Support for binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from aiocomelit.api import ComelitVedoAreaObject, ComelitVedoZoneObject
from aiocomelit.const import ALARM_AREA, ALARM_ZONE, AlarmAreaState, AlarmZoneState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ObjectClassType
from .coordinator import ComelitConfigEntry, ComelitSerialBridge, ComelitVedoSystem
from .utils import new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ComelitBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Comelit binary sensor entity description."""

    object_type: str
    is_on_fn: Callable[[ComelitVedoAreaObject | ComelitVedoZoneObject], bool]
    available_fn: Callable[[ComelitVedoAreaObject | ComelitVedoZoneObject], bool] = (
        lambda obj: True
    )


BINARY_SENSOR_TYPES: Final[tuple[ComelitBinarySensorEntityDescription, ...]] = (
    ComelitBinarySensorEntityDescription(
        key="anomaly",
        translation_key="anomaly",
        object_type=ALARM_AREA,
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda obj: cast(ComelitVedoAreaObject, obj).anomaly,
        available_fn=lambda obj: (
            cast(ComelitVedoAreaObject, obj).human_status != AlarmAreaState.UNKNOWN
        ),
    ),
    ComelitBinarySensorEntityDescription(
        key="presence",
        translation_key="motion",
        object_type=ALARM_ZONE,
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda obj: cast(ComelitVedoZoneObject, obj).status_api == "0001",
        available_fn=lambda obj: (
            cast(ComelitVedoZoneObject, obj).human_status
            not in {
                AlarmZoneState.FAULTY,
                AlarmZoneState.UNAVAILABLE,
                AlarmZoneState.UNKNOWN,
            }
        ),
    ),
    ComelitBinarySensorEntityDescription(
        key="faulty",
        translation_key="faulty",
        object_type=ALARM_ZONE,
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda obj: (
            cast(ComelitVedoZoneObject, obj).human_status == AlarmZoneState.FAULTY
        ),
        available_fn=lambda obj: (
            cast(ComelitVedoZoneObject, obj).human_status
            not in {
                AlarmZoneState.UNAVAILABLE,
                AlarmZoneState.UNKNOWN,
            }
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit VEDO binary sensors."""

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
            ComelitVedoBinarySensorEntity(
                coordinator,
                device,
                config_entry.entry_id,
                description,
            )
            for description in BINARY_SENSOR_TYPES
            for device in coordinator.data[dev_type].values()
            if description.object_type == dev_type
            if device in new_devices
        ]
        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        new_device_listener(coordinator, _add_new_entities, ALARM_AREA)
    )
    config_entry.async_on_unload(
        new_device_listener(coordinator, _add_new_entities, ALARM_ZONE)
    )


class ComelitVedoBinarySensorEntity(
    CoordinatorEntity[ComelitVedoSystem | ComelitSerialBridge], BinarySensorEntity
):
    """Sensor device."""

    entity_description: ComelitBinarySensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ComelitVedoSystem | ComelitSerialBridge,
        object_data: ComelitVedoAreaObject | ComelitVedoZoneObject,
        config_entry_entry_id: str,
        description: ComelitBinarySensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self.entity_description = description
        self._object_index = object_data.index
        self._object_type = description.object_type
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = (
            f"{config_entry_entry_id}-{description.key}-{self._object_index}"
        )
        self._attr_device_info = coordinator.platform_device_info(
            object_data, "area" if self._object_type == ALARM_AREA else "zone"
        )

    @property
    def _object(self) -> ComelitVedoAreaObject | ComelitVedoZoneObject:
        """Return alarm object."""
        return cast(
            ComelitVedoAreaObject | ComelitVedoZoneObject,
            self.coordinator.data[self._object_type][self._object_index],
        )

    @property
    def available(self) -> bool:
        """Return True if object is available."""
        if not self.entity_description.available_fn(self._object):
            return False
        return super().available

    @property
    def is_on(self) -> bool:
        """Return object binary sensor state."""
        return self.entity_description.is_on_fn(self._object)
