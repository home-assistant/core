"""Support for SolarEdge Modbus binary sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from solaredged import (
    Battery,
    BatteryStatus,
    Inverter,
    InverterExtended,
    InverterStatus,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SolarEdgeModbusConfigEntry
from .entity import SolarEdgeModbusBatteryEntity, SolarEdgeModbusInverterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusBinarySensorEntityDescription[ComponentT](
    BinarySensorEntityDescription
):
    """Describes a SolarEdge Modbus binary sensor entity."""

    exists_fn: Callable[[ComponentT], bool] = lambda _: True
    is_on_fn: Callable[[ComponentT], bool | None]


def _faulted(inverter: Inverter) -> bool | None:
    """Whether the inverter reports a fault, unknown while its status is."""
    if inverter.status is None:
        return None
    return inverter.status is InverterStatus.FAULT


def _charging(battery: Battery) -> bool | None:
    """Whether the battery is taking charge, unknown while its status is."""
    if battery.status is None:
        return None
    return battery.status is BatteryStatus.CHARGE


INVERTER_BINARY_SENSORS: tuple[
    SolarEdgeModbusBinarySensorEntityDescription[Inverter], ...
] = (
    SolarEdgeModbusBinarySensorEntityDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_faulted,
    ),
    SolarEdgeModbusBinarySensorEntityDescription(
        key="on_grid",
        translation_key="on_grid",
        # Grid status is a firmware extension; without it there is nothing to
        # show, and the library only carries the field where it answered.
        exists_fn=lambda inverter: isinstance(inverter, InverterExtended),
        is_on_fn=lambda inverter: inverter.on_grid,
    ),
)

BATTERY_BINARY_SENSORS: tuple[
    SolarEdgeModbusBinarySensorEntityDescription[Battery], ...
] = (
    # The status sensor carries the whole story, but Home Assistant's
    # battery-charging triggers and conditions only look at this device class.
    SolarEdgeModbusBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus binary sensor entities based on a config entry."""
    solaredge = entry.runtime_data.solaredge

    entities: list[BinarySensorEntity] = [
        SolarEdgeModbusInverterBinarySensorEntity(entry=entry, description=description)
        for description in INVERTER_BINARY_SENSORS
        if description.exists_fn(solaredge.inverter)
    ]
    entities.extend(
        SolarEdgeModbusBatteryBinarySensorEntity(
            entry=entry, description=description, index=index
        )
        for index in range(1, len(solaredge.batteries) + 1)
        for description in BATTERY_BINARY_SENSORS
        if description.exists_fn(solaredge.batteries[index - 1])
    )

    async_add_entities(entities)


class SolarEdgeModbusInverterBinarySensorEntity(
    SolarEdgeModbusInverterEntity, BinarySensorEntity
):
    """Defines a SolarEdge Modbus inverter binary sensor entity."""

    entity_description: SolarEdgeModbusBinarySensorEntityDescription[Inverter]

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.solaredge.inverter)


class SolarEdgeModbusBatteryBinarySensorEntity(
    SolarEdgeModbusBatteryEntity, BinarySensorEntity
):
    """Defines a SolarEdge Modbus battery binary sensor entity."""

    entity_description: SolarEdgeModbusBinarySensorEntityDescription[Battery]

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(
            self.coordinator.solaredge.batteries[self._index - 1]
        )
