"""Get ride details and liveboard details for NMBS (Belgian railway)."""

from datetime import datetime
from typing import Any, override

from pyrail.models import ConnectionDetails, LiveboardDeparture, StationDetails

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    EntityStateAttribute,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONNECTION_FEED,
    CONNECTION_UNIQUE_ID_PREFIX,
    LIVEBOARD_UNIQUE_ID_PREFIX,
)
from .coordinator import NMBSConfigEntry, NMBSCoordinator
from .entity import NMBSEntity

PARALLEL_UPDATES = 0

DEFAULT_ICON = "mdi:train"
DEFAULT_ICON_ALERT = "mdi:alert-octagon"


def get_time_until(departure_time: datetime) -> int:
    """Calculate the minutes between now and a train's departure time."""
    delta = dt_util.as_utc(departure_time) - dt_util.utcnow()
    return round(delta.total_seconds() / 60)


def get_delay_in_minutes(delay: int) -> int:
    """Get the delay in minutes from a delay in seconds."""
    return round(delay / 60)


def get_ride_duration(
    departure_time: datetime, arrival_time: datetime, delay: int
) -> int:
    """Calculate the total travel time in minutes."""
    duration = arrival_time - departure_time
    return round(duration.total_seconds() / 60) + get_delay_in_minutes(delay)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NMBSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NMBS sensor entities based on a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        [
            NMBSSensor(coordinator),
            NMBSLiveBoard(coordinator, coordinator.station_from),
            NMBSLiveBoard(coordinator, coordinator.station_to),
        ]
    )


class NMBSSensor(NMBSEntity, SensorEntity):
    """Get the total travel time for a given connection."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator: NMBSCoordinator) -> None:
        """Initialize the NMBS connection sensor."""
        super().__init__(coordinator)
        self._location: dict[str, float] = (
            {
                EntityStateAttribute.LATITUDE: coordinator.station_from.latitude,
                EntityStateAttribute.LONGITUDE: coordinator.station_from.longitude,
            }
            if coordinator.config_entry.data.get(CONF_SHOW_ON_MAP, False)
            else {}
        )
        self._attr_translation_key = "connection"
        self._attr_translation_placeholders = {
            "station_from": coordinator.station_from.standard_name,
            "station_to": coordinator.station_to.standard_name,
        }
        if custom_name := coordinator.config_entry.data.get(CONF_NAME):
            self._attr_name = custom_name
        unique_id = f"{coordinator.station_from.id}_{coordinator.station_to.id}"
        vias = "_excl_vias" if coordinator.exclude_vias else ""
        self._attr_unique_id = f"{CONNECTION_UNIQUE_ID_PREFIX}{unique_id}{vias}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain

    @property
    @override
    def available(self) -> bool:
        """Return True if the coordinator and the connection feed succeeded."""
        return (
            super().available
            and CONNECTION_FEED not in self.coordinator.data.failed_feeds
        )

    @property
    def connection(self) -> ConnectionDetails | None:
        """Return the current connection data."""
        return self.coordinator.data.connection

    @property
    @override
    def icon(self) -> str:
        """Return the sensor default icon or an alert icon if any delay."""
        if (connection := self.connection) and get_delay_in_minutes(
            connection.departure.delay
        ) > 0:
            return DEFAULT_ICON_ALERT
        return DEFAULT_ICON

    @property
    @override
    def native_value(self) -> int | None:
        """Return the travel time in minutes."""
        if (connection := self.connection) is None:
            return None
        return get_ride_duration(
            connection.departure.time,
            connection.arrival.time,
            connection.departure.delay,
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return sensor attributes, or only the map location when there is no connection.

        The departure and delay attributes are text forms of
        departure_minutes and delay_minutes, kept for existing templates.
        """
        if (connection := self.connection) is None:
            return self._location or None

        delay = get_delay_in_minutes(connection.departure.delay)
        departure = get_time_until(connection.departure.time)

        attrs: dict[str, Any] = {
            "destination": connection.arrival.station,
            "direction": connection.departure.direction.name,
            "platform_arriving": connection.arrival.platform,
            "platform_departing": connection.departure.platform,
            "vehicle_id": connection.departure.vehicle,
            "departure_time": connection.departure.time,
        }

        attrs["canceled"] = connection.departure.canceled
        if attrs["canceled"]:
            attrs["departure"] = None
            attrs["departure_minutes"] = None
        else:
            attrs["departure"] = f"In {departure} minutes"
            attrs["departure_minutes"] = departure

        attrs.update(self._location)

        if connection.vias and not self.coordinator.exclude_vias:
            via = connection.vias[0]

            attrs["via"] = via.station
            attrs["via_arrival_platform"] = via.arrival.platform
            attrs["via_transfer_platform"] = via.departure.platform
            attrs["via_transfer_time"] = get_delay_in_minutes(
                via.timebetween
            ) + get_delay_in_minutes(via.departure.delay)

        attrs["delay_seconds"] = connection.departure.delay
        attrs["delay"] = f"{delay} minutes"
        attrs["delay_minutes"] = delay

        return attrs


class NMBSLiveBoard(NMBSEntity, SensorEntity):
    """Get the next train from a station's liveboard."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: NMBSCoordinator, station: StationDetails) -> None:
        """Initialize the sensor for getting liveboard data."""
        super().__init__(coordinator)
        self._station = station
        self._attr_translation_key = "liveboard"
        self._attr_translation_placeholders = {"station": station.standard_name}
        unique_id = (
            f"{station.id}_{coordinator.station_from.id}_{coordinator.station_to.id}"
        )
        vias = "_excl_vias" if coordinator.exclude_vias else ""
        self._attr_unique_id = f"{LIVEBOARD_UNIQUE_ID_PREFIX}{unique_id}{vias}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain

    @property
    @override
    def available(self) -> bool:
        """Return True if the coordinator and the liveboard feed succeeded."""
        return (
            super().available
            and self._station.id not in self.coordinator.data.failed_feeds
        )

    @property
    def next_departure(self) -> LiveboardDeparture | None:
        """Return the next departure for the monitored station."""
        return self.coordinator.data.next_departures[self._station.id]

    @property
    @override
    def icon(self) -> str:
        """Return the default icon or an alert icon if the next departure is delayed."""
        if (departure := self.next_departure) and departure.delay > 0:
            return DEFAULT_ICON_ALERT
        return DEFAULT_ICON

    @property
    @override
    def native_value(self) -> str | None:
        """Return the track and destination of the next departure."""
        if (departure := self.next_departure) is None:
            return None
        return f"Track {departure.platform} - {departure.station}"

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the sensor attributes if data is available.

        The departure and delay attributes are text forms of
        departure_minutes and delay_minutes, kept for existing templates.
        """
        if (departure := self.next_departure) is None:
            return None

        delay = get_delay_in_minutes(departure.delay)
        departure_minutes = get_time_until(departure.time)

        attrs: dict[str, Any] = {
            "departure_time": departure.time,
            "departure": f"In {departure_minutes} minutes",
            "departure_minutes": departure_minutes,
            "extra_train": departure.is_extra,
            "vehicle_id": departure.vehicle,
            "monitored_station": self._station.standard_name,
        }

        if departure.delay > 0:
            attrs["delay_seconds"] = departure.delay
        if delay > 0:
            attrs["delay"] = f"{delay} minutes"
            attrs["delay_minutes"] = delay

        return attrs
