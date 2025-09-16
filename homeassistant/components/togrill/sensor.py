"""Support for sensor entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from togrill_bluetooth.packets import Packet, PacketA0Notify, PacketA1Notify

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ToGrillConfigEntry
from .const import CONF_PROBE_COUNT, MAX_PROBE_COUNT
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class ToGrillSensorEntityDescription(SensorEntityDescription):
    """Description of entity."""

    packet_type: int
    packet_extract: Callable[[Packet], StateType]
    entity_supported: Callable[[Mapping[str, Any]], bool] = lambda _: True
    probe_number: int | None = None


def _get_temperature_description(probe_number: int):
    def _get(packet: Packet) -> StateType:
        assert isinstance(packet, PacketA1Notify)
        if len(packet.temperatures) < probe_number:
            return None
        temperature = packet.temperatures[probe_number - 1]
        if temperature is None:
            return None
        return temperature

    def _supported(config: Mapping[str, Any]):
        return probe_number <= config[CONF_PROBE_COUNT]

    return ToGrillSensorEntityDescription(
        key=f"temperature_{probe_number}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        packet_type=PacketA1Notify.type,
        packet_extract=_get,
        entity_supported=_supported,
        probe_number=probe_number,
    )


ENTITY_DESCRIPTIONS = (
    ToGrillSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        packet_type=PacketA0Notify.type,
        packet_extract=lambda packet: cast(PacketA0Notify, packet).battery,
    ),
    *[
        _get_temperature_description(probe_number)
        for probe_number in range(1, MAX_PROBE_COUNT + 1)
    ],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        ToGrillSensor(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        if entity_description.entity_supported(entry.data)
    )


class ToGrillSensor(ToGrillEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: ToGrillSensorEntityDescription

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
        entity_description: ToGrillSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""

        super().__init__(coordinator, entity_description.probe_number)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> StateType:
        """Get current value."""
        if packet := self.coordinator.data.get(
            (self.entity_description.packet_type, None)
        ):
            return self.entity_description.packet_extract(packet)
        return None
