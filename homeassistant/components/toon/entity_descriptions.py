"""Entity descriptions for Toon entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntityDescription,
)
from homeassistant.components.switch import SwitchEntityDescription

from .binary_sensor import (
    ToonBinarySensor,
    ToonBoilerBinarySensor,
    ToonBoilerModuleBinarySensor,
    ToonDisplayBinarySensor,
)
from .switch import ToonHolidayModeSwitch, ToonProgramSwitch, ToonSwitch


@dataclass
class ToonRequiredKeysMixin:
    """Mixin for required keys."""

    section: str
    measurement: str


@dataclass
class ToonBinarySensorRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for binary sensor required keys."""

    cls: type[ToonBinarySensor]


@dataclass
class ToonBinarySensorEntityDescription(
    BinarySensorEntityDescription, ToonBinarySensorRequiredKeysMixin
):
    """Describes Toon binary sensor entity."""

    inverted: bool = False


BINARY_SENSOR_ENTITIES = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_boiler_connected_None",
        name="Boiler Module Connection",
        section="thermostat",
        measurement="boiler_module_connected",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        entity_registry_enabled_default=False,
        cls=ToonBoilerModuleBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_program_overridden",
        name="Thermostat Program Override",
        section="thermostat",
        measurement="program_overridden",
        icon="mdi:gesture-tap",
        cls=ToonDisplayBinarySensor,
    ),
)

BINARY_SENSOR_ENTITIES_BOILER: tuple[ToonBinarySensorEntityDescription, ...] = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_1",
        name="Boiler Heating",
        section="thermostat",
        measurement="heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_2",
        name="Hot Tap Water",
        section="thermostat",
        measurement="hot_tapwater",
        icon="mdi:water-pump",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_3",
        name="Boiler Preheating",
        section="thermostat",
        measurement="pre_heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_None",
        name="Boiler Burner",
        section="thermostat",
        measurement="burner",
        icon="mdi:fire",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_error_found_255",
        name="Boiler Status",
        section="thermostat",
        measurement="error_found",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:alert",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_ot_communication_error_0",
        name="OpenTherm Connection",
        section="thermostat",
        measurement="opentherm_communication_error",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:check-network-outline",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
)


@dataclass
class ToonSwitchRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for switch required keys."""

    cls: type[ToonSwitch]


@dataclass
class ToonSwitchEntityDescription(SwitchEntityDescription, ToonSwitchRequiredKeysMixin):
    """Describes Toon switch entity."""


SWITCH_ENTITIES: tuple[ToonSwitchEntityDescription, ...] = (
    ToonSwitchEntityDescription(
        key="thermostat_holiday_mode",
        name="Holiday Mode",
        section="thermostat",
        measurement="holiday_mode",
        icon="mdi:airport",
        cls=ToonHolidayModeSwitch,
    ),
    ToonSwitchEntityDescription(
        key="thermostat_program",
        name="Thermostat Program",
        section="thermostat",
        measurement="program",
        icon="mdi:calendar-clock",
        cls=ToonProgramSwitch,
    ),
)
