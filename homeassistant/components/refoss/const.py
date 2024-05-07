"""const."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from logging import Logger, getLogger

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)

_LOGGER: Logger = getLogger(__package__)

COORDINATORS = "coordinators"

DATA_DISCOVERY_SERVICE = "refoss_discovery"

DISCOVERY_SCAN_INTERVAL = 30
DISCOVERY_TIMEOUT = 8
DISPATCH_DEVICE_DISCOVERED = "refoss_device_discovered"
DISPATCHERS = "dispatchers"

DOMAIN = "refoss"
COORDINATOR = "coordinator"

MAX_ERRORS = 2

ENERGY = "energy"
ENERGY_RETURNED = "energy_returned"


@dataclass
class UnitOfMeasurement:
    """Describes a unit of measurement."""

    unit: str
    device_classes: set[str]
    aliases: set[str] = field(default_factory=set)
    conversion_unit: str | None = None
    conversion_fn: Callable[[float], str] | None = None


UNITS = (
    UnitOfMeasurement(
        unit=UnitOfElectricPotential.VOLT,
        aliases={"v"},
        device_classes={SensorDeviceClass.VOLTAGE},
        conversion_fn=lambda x: f"{x / 1000:.2f}",
    ),
    UnitOfMeasurement(
        unit=UnitOfElectricCurrent.AMPERE,
        aliases={"a"},
        device_classes={SensorDeviceClass.CURRENT},
        conversion_fn=lambda x: f"{x / 1000:.2f}",
    ),
    UnitOfMeasurement(
        unit=UnitOfPower.WATT,
        aliases={"w"},
        device_classes={SensorDeviceClass.POWER},
        conversion_fn=lambda x: f"{x / 1000:.2f}",
    ),
    UnitOfMeasurement(
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        aliases={"kwh"},
        device_classes={SensorDeviceClass.ENERGY},
        conversion_fn=lambda x: f"{x / 1000:.2f}",
    ),
)


DEVICE_CLASS_UNITS: dict[str, dict[str, UnitOfMeasurement]] = {}
for uom in UNITS:
    for device_class in uom.device_classes:
        DEVICE_CLASS_UNITS.setdefault(device_class, {})[uom.unit] = uom
        for unit_alias in uom.aliases:
            DEVICE_CLASS_UNITS[device_class][unit_alias] = uom


CHANNEL_DISPLAY_NAME: dict[str, dict[int, str]] = {
    "em06": {
        1: "A1",
        2: "B1",
        3: "C1",
        4: "A2",
        5: "B2",
        6: "C2",
    }
}
