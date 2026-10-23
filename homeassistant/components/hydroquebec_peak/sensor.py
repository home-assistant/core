"""Sensors for the Hydro-Québec Peak Events integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from hydropeak_opendata import PeakEvent

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HydroQuebecPeakConfigEntry
from .entity import HydroQuebecPeakEntity

# The coordinator handles all I/O; entities only read its data
PARALLEL_UPDATES = 0


def _current_or_next_event(events: tuple[PeakEvent, ...]) -> PeakEvent | None:
    """Return the event in progress, or the next upcoming one."""
    now = dt_util.utcnow()
    return next(
        (event for event in events if event.is_active(now)),
        next((event for event in events if event.start > now), None),
    )


@dataclass(frozen=True, kw_only=True)
class HydroQuebecPeakSensorDescription(SensorEntityDescription):
    """Describes a Hydro-Québec peak event sensor."""

    value_fn: Callable[[PeakEvent], datetime]


SENSORS: tuple[HydroQuebecPeakSensorDescription, ...] = (
    HydroQuebecPeakSensorDescription(
        key="event_begin",
        translation_key="event_begin",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda event: event.start,
    ),
    HydroQuebecPeakSensorDescription(
        key="event_end",
        translation_key="event_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda event: event.end,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydroQuebecPeakConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        HydroQuebecPeakSensor(entry.runtime_data, description)
        for description in SENSORS
    )


class HydroQuebecPeakSensor(HydroQuebecPeakEntity, SensorEntity):
    """Timestamp of the current or next peak event."""

    entity_description: HydroQuebecPeakSensorDescription

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the timestamp for the current or next event, if any."""
        event = _current_or_next_event(self.coordinator.data)
        if event is None:
            return None
        return self.entity_description.value_fn(event)
