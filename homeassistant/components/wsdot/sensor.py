"""Support for Washington State Department of Transportation (WSDOT) data."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol
import wsdot

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by WSDOT"

CONF_TRAVEL_TIMES = "travel_time"

ICON = "mdi:car"

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TRAVEL_TIMES): [
            {vol.Required(CONF_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
        ],
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the WSDOT sensor."""
    sensors = []
    for travel_time in config[CONF_TRAVEL_TIMES]:
        name = travel_time.get(CONF_NAME) or travel_time.get(CONF_ID)
        sensors.append(
            WashingtonStateTravelTimeSensor(
                name, hass, config[CONF_API_KEY], travel_time.get(CONF_ID)
            )
        )

    add_entities(sensors, True)


class WashingtonStateTransportSensor(SensorEntity):
    """Sensor that reads the WSDOT web API.

    WSDOT provides ferry schedules, toll rates, weather conditions,
    mountain pass conditions, and more. Subclasses of this
    can read them and make them available.
    """

    _attr_icon = ICON

    def __init__(self, name: str) -> None:
        """Initialize the sensor."""
        self._name = name
        self._state: int | None = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state


class WashingtonStateTravelTimeSensor(WashingtonStateTransportSensor):
    """Travel time sensor from WSDOT."""

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, name: str, hass: HomeAssistant, access_code: str, travel_time_id: str) -> None:
        """Construct a travel time sensor."""
        super().__init__(name)
        self._data: wsdot.TravelTime | None = None
        self._travel_time_id = travel_time_id
        self._access_code = access_code
        self.hass = hass
        self._wsdot_travel: wsdot.WsdotTravelTimes | None = None

    @property
    def wsdot_travel(self) -> wsdot.WsdotTravelTimes:
        """Return a cached WsdotTravelTimes object."""
        if self._wsdot_travel is None:
            session = async_get_clientsession(self.hass)
            self._wsdot_travel = wsdot.WsdotTravelTimes(api_key=self._access_code, session=session)
        return self._wsdot_travel

    async def async_update(self) -> None:
        """Get the latest data from WSDOT."""
        try:
            travel_time = await self.wsdot_travel.get_travel_time(self._travel_time_id)
        except wsdot.WsdotTravelError:
            _LOGGER.warning("Invalid response from WSDOT API")
        else:
            self._data = travel_time
            self._state = travel_time.CurrentTime

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return other details about the sensor state."""
        if self._data is not None:
            return self._data.dict()
        return None
