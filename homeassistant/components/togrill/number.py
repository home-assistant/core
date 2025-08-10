"""Support for number entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from togrill_bluetooth.packets import (
    PacketA0Notify,
    PacketA6Write,
    PacketA8Notify,
    PacketA301Write,
    PacketWrite,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ToGrillConfigEntry
from .const import CONF_PROBE_COUNT, MAX_PROBE_COUNT
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class ToGrillSensorEntityDescription(NumberEntityDescription):
    """Description of entity."""

    get_value: Callable[[ToGrillCoordinator], float | None]
    set_packet: Callable[[float], PacketWrite]
    entity_supported: Callable[[Mapping[str, Any]], bool] = lambda _: True


def _get_temperature_target_description(probe_number: int):
    def _set_packet(value: float | None) -> PacketWrite:
        if value == 0.0:
            value = None
        return PacketA301Write(probe=probe_number, target=value)

    def _get_value(coordinator: ToGrillCoordinator) -> float | None:
        if packet := coordinator.get_packet(PacketA8Notify, probe_number):
            if packet.alarm_type == PacketA8Notify.AlarmType.TEMPERATURE_TARGET:
                return packet.temperature_1
        return None

    def _supported(config: Mapping[str, Any]):
        return probe_number <= config[CONF_PROBE_COUNT]

    return ToGrillSensorEntityDescription(
        key=f"temperature_target_{probe_number}",
        translation_key="temperature_target",
        translation_placeholders={"probe_number": f"{probe_number}"},
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=250,
        mode=NumberMode.BOX,
        set_packet=_set_packet,
        get_value=_get_value,
        entity_supported=_supported,
    )


ENTITY_DESCRIPTIONS = (
    *[
        _get_temperature_target_description(probe_number)
        for probe_number in range(1, MAX_PROBE_COUNT + 1)
    ],
    ToGrillSensorEntityDescription(
        key="alarm_interval",
        translation_key="alarm_interval",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=15,
        native_step=5,
        mode=NumberMode.BOX,
        set_packet=lambda x: PacketA6Write(
            temperature_unit=None, alarm_interval=round(x)
        ),
        get_value=lambda x: packet.alarm_interval
        if (packet := x.get_packet(PacketA0Notify))
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gardena Bluetooth sensor based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        ToGrillNumber(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        if entity_description.entity_supported(entry.data)
    )


class ToGrillNumber(ToGrillEntity, NumberEntity):
    """Representation of a sensor."""

    entity_description: ToGrillSensorEntityDescription

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
        entity_description: ToGrillSensorEntityDescription,
    ) -> None:
        """Initialize sensor."""

        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.get_value(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set value on device."""

        packet = self.entity_description.set_packet(value)
        await self._write_packet(packet)
