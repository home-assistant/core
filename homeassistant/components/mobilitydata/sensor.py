"""Sensor platform for the MobilityData integration.

Three timestamp sensors per configured stop — the next three departures —
honoring the stop subentry's route and headsign filters.
"""

from datetime import datetime
from typing import Any, override

from aiomobilitydatabase.feeds import StopArrival

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_FEED_ID, CONF_STOP_IDS, CONF_STOP_NAME, DOMAIN
from .coordinator import ArrivalsCoordinator, MobilityDataConfigEntry, stop_subentries

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MobilityDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up departure sensors for each stop subentry."""
    coordinator = entry.runtime_data.arrivals_coordinator
    for subentry_id, subentry in stop_subentries(entry).items():
        async_add_entities(
            [
                MobilityDataDepartureSensor(coordinator, subentry, index)
                for index in range(3)
            ],
            config_subentry_id=subentry_id,
        )


class MobilityDataDepartureSensor(CoordinatorEntity[ArrivalsCoordinator], SensorEntity):
    """An upcoming departure at a configured stop."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: ArrivalsCoordinator,
        subentry: ConfigSubentry,
        index: int,
    ) -> None:
        """Initialize the departure sensor."""
        super().__init__(coordinator)
        self._subentry = subentry
        self._index = index
        self._attr_translation_key = (
            "next_departure",
            "second_departure",
            "third_departure",
        )[index]
        self._attr_entity_registry_enabled_default = index == 0
        self._attr_unique_id = f"{subentry.subentry_id}_departure_{index}"
        feed_id: str = coordinator.config_entry.data[CONF_FEED_ID]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{feed_id}_{subentry.unique_id}")},
            name=subentry.data[CONF_STOP_NAME],
            manufacturer=coordinator.config_entry.title,
            model="Transit stop",
        )

    def _arrival(self) -> StopArrival | None:
        arrivals = (self.coordinator.data or {}).get(self._subentry.subentry_id) or []
        if len(arrivals) > self._index:
            return arrivals[self._index]
        return None

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the stop is gone from the current dataset."""
        return super().available and bool(
            self.coordinator.static_coordinator.stop_ids.intersection(
                self._subentry.data[CONF_STOP_IDS]
            )
        )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the effective departure time."""
        if (arrival := self._arrival()) is None:
            return None
        return arrival.predicted_departure or arrival.scheduled_departure

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the departure's route, headsign, and realtime details."""
        if (arrival := self._arrival()) is None:
            return None
        return {
            "route_id": arrival.route_id,
            "route_name": arrival.route_name,
            "headsign": arrival.headsign,
            "scheduled_departure": arrival.scheduled_departure,
            "predicted_departure": arrival.predicted_departure,
            "delay_seconds": arrival.delay_seconds,
            "realtime": arrival.realtime,
            "trip_id": arrival.trip_id,
        }
