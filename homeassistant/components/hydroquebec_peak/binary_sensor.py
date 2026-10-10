"""Binary sensors for the Hydro-Québec Peak Events integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import override

from hydropeak_opendata import PeakEvent

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HydroQuebecPeakConfigEntry
from .entity import HydroQuebecPeakEntity

# The coordinator handles all I/O; entities only read its data
PARALLEL_UPDATES = 0


def _peak_on_day(events: tuple[PeakEvent, ...], day: date, period: str) -> bool:
    """Whether an event of the given period starts on the given local day."""
    return any(
        event.period == period and dt_util.as_local(event.start).date() == day
        for event in events
    )


@dataclass(frozen=True, kw_only=True)
class HydroQuebecPeakBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Hydro-Québec peak event binary sensor."""

    value_fn: Callable[[tuple[PeakEvent, ...]], bool]


BINARY_SENSORS: tuple[HydroQuebecPeakBinarySensorDescription, ...] = (
    HydroQuebecPeakBinarySensorDescription(
        key="peak_active",
        translation_key="peak_active",
        value_fn=lambda events: any(
            event.is_active(dt_util.utcnow()) for event in events
        ),
    ),
    HydroQuebecPeakBinarySensorDescription(
        key="peak_today_am",
        translation_key="peak_today_am",
        value_fn=lambda events: _peak_on_day(events, dt_util.now().date(), "AM"),
    ),
    HydroQuebecPeakBinarySensorDescription(
        key="peak_today_pm",
        translation_key="peak_today_pm",
        value_fn=lambda events: _peak_on_day(events, dt_util.now().date(), "PM"),
    ),
    HydroQuebecPeakBinarySensorDescription(
        key="peak_tomorrow_am",
        translation_key="peak_tomorrow_am",
        value_fn=lambda events: _peak_on_day(
            events, dt_util.now().date() + timedelta(days=1), "AM"
        ),
    ),
    HydroQuebecPeakBinarySensorDescription(
        key="peak_tomorrow_pm",
        translation_key="peak_tomorrow_pm",
        value_fn=lambda events: _peak_on_day(
            events, dt_util.now().date() + timedelta(days=1), "PM"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroQuebecPeakConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities(
        HydroQuebecPeakBinarySensor(entry.runtime_data, description)
        for description in BINARY_SENSORS
    )


class HydroQuebecPeakBinarySensor(HydroQuebecPeakEntity, BinarySensorEntity):
    """State of peak events for one offer."""

    entity_description: HydroQuebecPeakBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool:
        """Return the computed state."""
        return self.entity_description.value_fn(self.coordinator.data)
