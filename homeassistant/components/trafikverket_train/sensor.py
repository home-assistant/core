"""Train information for departures and delays, provided by Trafikverket."""
from __future__ import annotations

from datetime import time, timedelta
from typing import TYPE_CHECKING

from pytrafikverket.trafikverket_train import StationInfo

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_WEEKDAY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_TIME, DOMAIN
from .coordinator import TVDataUpdateCoordinator
from .util import create_unique_id

ATTR_DEPARTURE_STATE = "departure_state"
ATTR_CANCELED = "canceled"
ATTR_DELAY_TIME = "number_of_minutes_delayed"
ATTR_PLANNED_TIME = "planned_time"
ATTR_ESTIMATED_TIME = "estimated_time"
ATTR_ACTUAL_TIME = "actual_time"
ATTR_OTHER_INFORMATION = "other_information"
ATTR_DEVIATIONS = "deviations"

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator: TVDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    to_station = coordinator.to_station
    from_station = coordinator.from_station
    get_time: str | None = entry.data.get(CONF_TIME)
    train_time = dt_util.parse_time(get_time) if get_time else None

    async_add_entities(
        [
            TrainSensor(
                coordinator,
                entry.data[CONF_NAME],
                from_station,
                to_station,
                entry.data[CONF_WEEKDAY],
                train_time,
                entry.entry_id,
            )
        ],
        True,
    )


class TrainSensor(CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity):
    """Contains data about a train depature."""

    _attr_icon = ICON
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        name: str,
        from_station: StationInfo,
        to_station: StationInfo,
        weekday: list,
        departuretime: time | None,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v2.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        if TYPE_CHECKING:
            assert from_station.name and to_station.name
        self._attr_unique_id = create_unique_id(
            from_station.name, to_station.name, departuretime, weekday
        )
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Retrieve latest state."""

        data = self.coordinator.data

        self._attr_native_value = data.departure_time

        self._attr_extra_state_attributes = {
            ATTR_DEPARTURE_STATE: data.departure_state,
            ATTR_CANCELED: data.cancelled,
            ATTR_DELAY_TIME: data.delayed_time,
            ATTR_PLANNED_TIME: data.planned_time,
            ATTR_ESTIMATED_TIME: data.estimated_time,
            ATTR_ACTUAL_TIME: data.actual_time,
            ATTR_OTHER_INFORMATION: data.other_info,
            ATTR_DEVIATIONS: data.deviation,
        }
