"""Sensor platform for MTA New York City Transit."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, CONF_STOP_ID, CONF_STOP_NAME, DOMAIN
from .coordinator import MTAConfigEntry, MTADataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MTAConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MTA sensor based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            MTAArrivalSensor(coordinator, entry, 0, "next_arrival"),
            MTAArrivalSensor(coordinator, entry, 1, "second_arrival"),
            MTAArrivalSensor(coordinator, entry, 2, "third_arrival"),
            MTAStopIDSensor(coordinator, entry),
        ]
    )


class MTAArrivalSensor(CoordinatorEntity[MTADataUpdateCoordinator], SensorEntity):
    """Sensor that displays MTA train arrival time."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:subway-variant"

    def __init__(
        self,
        coordinator: MTADataUpdateCoordinator,
        entry: MTAConfigEntry,
        arrival_index: int,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._arrival_index = arrival_index
        line = entry.data[CONF_LINE]
        stop_name = entry.data.get(CONF_STOP_NAME, entry.data[CONF_STOP_ID])

        self._attr_unique_id = f"{entry.unique_id}-{translation_key}"
        self._attr_translation_key = translation_key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{line} Line - {stop_name}",
            manufacturer="MTA",
            model="Subway",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        arrivals = self.coordinator.data.arrivals
        if len(arrivals) <= self._arrival_index:
            return None

        return arrivals[self._arrival_index].arrival_time

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional attributes."""
        arrivals = self.coordinator.data.arrivals
        if len(arrivals) <= self._arrival_index:
            return None

        arrival = arrivals[self._arrival_index]
        return {
            "route": arrival.route_id,
            "destination": arrival.destination,
        }


class MTAStopIDSensor(CoordinatorEntity[MTADataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor that displays the MTA stop ID."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(
        self,
        coordinator: MTADataUpdateCoordinator,
        entry: MTAConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        line = entry.data[CONF_LINE]
        stop_name = entry.data.get(CONF_STOP_NAME, entry.data[CONF_STOP_ID])

        self._attr_unique_id = f"{entry.unique_id}-stop_id"
        self._attr_translation_key = "stop_id"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{line} Line - {stop_name}",
            manufacturer="MTA",
            model="Subway",
            entry_type=DeviceEntryType.SERVICE,
        )

        self._stop_id = entry.data[CONF_STOP_ID]

    @property
    def native_value(self) -> str:
        """Return the stop ID."""
        return self._stop_id
