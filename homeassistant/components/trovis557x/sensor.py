"""Sensor platform — diagnostic readings (temperatures, status, valve position).

Setpoints live on the climate / water-heater entities; room and storage
temperatures are those entities' current temperature. What remains here is
diagnostic, and is routed to the controller or the per-circuit / hot-water
sub-device it belongs to.
"""

from dataclasses import dataclass
from enum import IntEnum

from trovis_modbus import OperatingMode

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TrovisConfigEntry, TrovisCoordinator
from .entity import TrovisEntity

_MODE_OPTIONS = [mode.name.lower() for mode in OperatingMode]


@dataclass(frozen=True, kw_only=True)
class TrovisSensorDescription(SensorEntityDescription):
    """Describes a sensor reading one attribute of one component."""

    component: str
    attribute: str


def _temp(
    component: str, attribute: str, name: str, *, enabled: bool = True
) -> TrovisSensorDescription:
    return TrovisSensorDescription(
        key=f"{component}_{attribute}",
        name=name,
        component=component,
        attribute=attribute,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _switch(component: str, attribute: str, name: str) -> TrovisSensorDescription:
    return TrovisSensorDescription(
        key=f"{component}_{attribute}",
        name=name,
        component=component,
        attribute=attribute,
        device_class=SensorDeviceClass.ENUM,
        options=_MODE_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


# Controller-level sensors.
_CONTROLLER: tuple[TrovisSensorDescription, ...] = (
    _temp("sensors", "outside_1", "Outside temperature"),
    _temp("sensors", "outside_2", "Outside temperature 2", enabled=False),
    _temp("sensors", "flow_4", "Flow temperature 4", enabled=False),
    _temp("sensors", "storage_remote", "Storage/remote temperature", enabled=False),
    _temp("sensors", "remote_1", "Remote adjuster 1", enabled=False),
    _temp("sensors", "remote_2", "Remote adjuster 2", enabled=False),
    _temp("controller", "max_flow_setpoint", "Max flow setpoint", enabled=False),
    _switch("controller", "switch_top", "Switch top"),
    _switch("controller", "switch_middle", "Switch middle"),
    _switch("controller", "switch_bottom", "Switch bottom"),
    TrovisSensorDescription(
        key="controller_error_status",
        name="Error status",
        component="controller",
        attribute="error_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Per-circuit sensors (attribute, name).
_CIRCUIT: tuple[tuple[str, str, bool], ...] = (
    ("flow_temperature", "Flow temperature", True),
    ("return_temperature", "Return temperature", True),
)

# Hot-water sensors.
_HOT_WATER: tuple[TrovisSensorDescription, ...] = (
    _temp("hot_water", "storage_temperature_lower", "Lower storage temperature"),
    _temp("hot_water", "active_charge_setpoint", "Charge setpoint", enabled=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrovisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Trovis sensors."""
    coordinator = entry.runtime_data
    entities = [TrovisSensor(coordinator, d) for d in (*_CONTROLLER, *_HOT_WATER)]
    for index in (1, 2, 3):
        component = f"heating_circuit_{index}"
        for attribute, name, enabled in _CIRCUIT:
            entities.append(
                TrovisSensor(
                    coordinator, _temp(component, attribute, name, enabled=enabled)
                )
            )
        entities.append(
            TrovisSensor(
                coordinator,
                TrovisSensorDescription(
                    key=f"{component}_control_signal",
                    name="Valve position",
                    component=component,
                    attribute="control_signal",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            )
        )
    async_add_entities(entities)


class TrovisSensor(TrovisEntity, SensorEntity):
    """A single value read from a component attribute."""

    entity_description: TrovisSensorDescription

    def __init__(
        self, coordinator: TrovisCoordinator, description: TrovisSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key, description.component)
        self.entity_description = description

    @property
    def native_value(self) -> object:
        """Return the current value, mapping enums to their lowercase name."""
        value = getattr(self._subsystem, self.entity_description.attribute)
        if isinstance(value, IntEnum):
            return value.name.lower()
        return value
