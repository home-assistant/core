"""Support for number entities."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from typing import Any

from togrill_bluetooth.packets import (
    AlarmType,
    PacketA0Notify,
    PacketA6Write,
    PacketA8Notify,
    PacketA300Write,
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
class ToGrillNumberEntityDescription(NumberEntityDescription):
    """Description of entity."""

    get_value: Callable[[ToGrillCoordinator], float | None]
    set_packet: Callable[[ToGrillCoordinator, float], PacketWrite]
    entity_supported: Callable[[Mapping[str, Any]], bool] = lambda _: True
    probe_number: int | None = None


def _get_temperature_descriptions(
    probe_number: int,
) -> Generator[ToGrillNumberEntityDescription]:
    def _get_description(
        variant: str,
        icon: str | None,
        set_packet: Callable[[ToGrillCoordinator, float], PacketWrite],
        get_value: Callable[[ToGrillCoordinator], float | None],
    ) -> ToGrillNumberEntityDescription:
        return ToGrillNumberEntityDescription(
            key=f"temperature_{variant}_{probe_number}",
            translation_key=f"temperature_{variant}",
            translation_placeholders={"probe_number": f"{probe_number}"},
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=0,
            native_max_value=250,
            mode=NumberMode.BOX,
            icon=icon,
            set_packet=set_packet,
            get_value=get_value,
            entity_supported=lambda x: probe_number <= x[CONF_PROBE_COUNT],
            probe_number=probe_number,
        )

    def _get_temperatures(
        coordinator: ToGrillCoordinator, alarm_type: AlarmType
    ) -> tuple[None | float, None | float]:
        if not (packet := coordinator.get_packet(PacketA8Notify, probe_number)):
            return None, None

        if packet.alarm_type != alarm_type:
            return None, None

        return packet.temperature_1, packet.temperature_2

    def _set_target(
        coordinator: ToGrillCoordinator, value: float | None
    ) -> PacketWrite:
        if value == 0.0:
            value = None
        return PacketA301Write(probe=probe_number, target=value)

    def _set_minimum(
        coordinator: ToGrillCoordinator, value: float | None
    ) -> PacketWrite:
        _, maximum = _get_temperatures(coordinator, AlarmType.TEMPERATURE_RANGE)
        if value == 0.0:
            value = None
        return PacketA300Write(probe=probe_number, minimum=value, maximum=maximum)

    def _set_maximum(
        coordinator: ToGrillCoordinator, value: float | None
    ) -> PacketWrite:
        minimum, _ = _get_temperatures(coordinator, AlarmType.TEMPERATURE_RANGE)
        if value == 0.0:
            value = None
        return PacketA300Write(probe=probe_number, minimum=minimum, maximum=value)

    yield _get_description(
        "target",
        "mdi:thermometer-check",
        _set_target,
        lambda x: _get_temperatures(x, AlarmType.TEMPERATURE_TARGET)[0],
    )
    yield _get_description(
        "minimum",
        "mdi:thermometer-chevron-down",
        _set_minimum,
        lambda x: _get_temperatures(x, AlarmType.TEMPERATURE_RANGE)[0],
    )
    yield _get_description(
        "maximum",
        "mdi:thermometer-chevron-up",
        _set_maximum,
        lambda x: _get_temperatures(x, AlarmType.TEMPERATURE_RANGE)[1],
    )


ENTITY_DESCRIPTIONS = (
    *[
        description
        for probe_number in range(1, MAX_PROBE_COUNT + 1)
        for description in _get_temperature_descriptions(probe_number)
    ],
    ToGrillNumberEntityDescription(
        key="alarm_interval",
        translation_key="alarm_interval",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=15,
        native_step=5,
        mode=NumberMode.BOX,
        set_packet=lambda coordinator, x: (
            PacketA6Write(temperature_unit=None, alarm_interval=round(x))
        ),
        get_value=lambda x: (
            packet.alarm_interval if (packet := x.get_packet(PacketA0Notify)) else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        ToGrillNumber(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
        if entity_description.entity_supported(entry.data)
    )


class ToGrillNumber(ToGrillEntity, NumberEntity):
    """Representation of a number."""

    entity_description: ToGrillNumberEntityDescription

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
        entity_description: ToGrillNumberEntityDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator, probe_number=entity_description.probe_number)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.get_value(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set value on device."""

        packet = self.entity_description.set_packet(self.coordinator, value)
        await self._write_packet(packet)
