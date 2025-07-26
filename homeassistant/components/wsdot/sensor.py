"""Support for Washington State Department of Transportation (WSDOT) data."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol
import wsdot as wsdot_api

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by WSDOT"

CONF_TRAVEL_TIMES = "travel_time"

ICON = "mdi:car"
DOMAIN = "wsdot"

SCAN_INTERVAL = timedelta(minutes=3)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TRAVEL_TIMES): [
            {vol.Required(CONF_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
        ],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Migrate a platform-style wsdot to entry-style."""
    # old-style config was entered by hand. make sure all values are valid
    api_key = config[CONF_API_KEY]
    session = async_get_clientsession(hass)
    try:
        # check for valid API Key
        wsdot_api.WsdotTravelTimes(
            api_key=api_key, session=session
        ).get_all_travel_times()
    except wsdot_api.WsdotTravelError as wsdot_error:
        raise PlatformNotReady from wsdot_error

    for old_entry in hass.config_entries.async_loaded_entries(DOMAIN):
        await hass.config_entries.async_remove(old_entry.entry_id)
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WSDOT sensor."""
    sensors = []
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    wsdot_travel = wsdot_api.WsdotTravelTimes(api_key=api_key, session=session)
    for travel_time in entry.data[CONF_TRAVEL_TIMES]:
        name = travel_time.get(CONF_NAME) or travel_time.get(CONF_ID)
        travel_time_id = int(travel_time[CONF_ID])
        sensors.append(
            WashingtonStateTravelTimeSensor(name, wsdot_travel, travel_time_id)
        )

    add_entities(sensors)


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

    def __init__(
        self, name: str, wsdot_travel: wsdot_api.WsdotTravelTimes, travel_time_id: int
    ) -> None:
        """Construct a travel time sensor."""
        super().__init__(name)
        self._data: wsdot_api.TravelTime | None = None
        self._travel_time_id = travel_time_id
        self._wsdot_travel = wsdot_travel

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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return other details about the sensor state."""
        if self._data is not None:
            return self._data.model_dump()
        return None
