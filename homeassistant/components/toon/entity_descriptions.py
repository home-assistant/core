"""Entity descriptions for Toon entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntityDescription

from .switch import ToonHolidayModeSwitch, ToonProgramSwitch, ToonSwitch


@dataclass
class ToonRequiredKeysMixin:
    """Mixin for required keys."""

    section: str
    measurement: str


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
