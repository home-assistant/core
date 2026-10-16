"""Support for Washington State Department of Transportation (WSDOT) data."""

from datetime import timedelta
import logging
from typing import Any, override

import wsdot as wsdot_api

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ID, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WsdotConfigEntry
from .const import ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:car"

SCAN_INTERVAL = timedelta(minutes=3)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WsdotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WSDOT sensor."""
    for subentry_id, subentry in entry.subentries.items():
        name = subentry.data[CONF_NAME]
        travel_time_id = subentry.data[CONF_ID]
        sensor = WashingtonStateTravelTimeSensor(
            name, entry.runtime_data, travel_time_id
        )
        async_add_entities(
            [sensor], config_subentry_id=subentry_id, update_before_add=True
        )


class WashingtonStateTransportSensor(SensorEntity):
    """Sensor that reads the WSDOT web API.

    WSDOT provides ferry schedules, toll rates, weather conditions,
    mountain pass conditions, and more. Subclasses of this
    can read them and make them available.
    """

    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON

    def __init__(self, name: str) -> None:
        """Initialize the sensor."""
        self._name = name
        self._state: int | None = None

    @property
    @override
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    @override
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state


class WashingtonStateTravelTimeSensor(WashingtonStateTransportSensor):
    """Travel time sensor from WSDOT."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self, name: str, wsdot_travel: wsdot_api.WsdotTravelTimes, travel_time_id: int
    ) -> None:
        """Construct a travel time sensor."""
        super().__init__(name)
        self._data: wsdot_api.TravelTime | None = None
        self._travel_time_id = travel_time_id
        self._wsdot_travel = wsdot_travel
        self._attr_unique_id = f"travel_time-{travel_time_id}"

    async def async_update(self) -> None:
        """Get the latest data from WSDOT."""
        try:
            travel_time = await self._wsdot_travel.get_travel_time(self._travel_time_id)
        except wsdot_api.WsdotTravelError:
            _LOGGER.warning("Invalid response from WSDOT API")
        else:
            self._data = travel_time
            self._state = travel_time.CurrentTime

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return other details about the sensor state."""
        if self._data is not None:
            return self._data.model_dump()
        return None
