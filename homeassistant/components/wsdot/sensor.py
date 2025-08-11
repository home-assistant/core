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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_SOURCE,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import WsdotConfigEntry, WsdotRuntimeData
from .const import ATTRIBUTION, CONF_TRAVEL_TIMES, DOMAIN

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Migrate a platform-style wsdot to entry-style."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        for entry in entries:
            _LOGGER.info(
                "Found already-setup WSDOT entry. Skipping platform setup. Your "
                'configuration.yaml might contain a "wsdot" entry in `sensor.platform` '
                "that is no longer needed"
            )
            if entry.data[CONF_API_KEY] != config[CONF_API_KEY]:
                _LOGGER.warning(
                    "Legacy Platform WSDOT entry found but there already exists a WSDOT "
                    "entry with a different API Key. Skipping migration of this configuration"
                )
        return

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WsdotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WSDOT sensor."""
    session = async_get_clientsession(hass)
    api_key = entry.data[CONF_API_KEY]
    wsdot_travel_times = wsdot_api.WsdotTravelTimes(api_key=api_key, session=session)
    try:
        await wsdot_travel_times.get_all_travel_times()
    except wsdot_api.WsdotError as api_error:
        raise ConfigEntryAuthFailed from api_error
    entry.runtime_data = WsdotRuntimeData(wsdot_travel_times=wsdot_travel_times)
    for subentry_id, subentry in entry.subentries.items():
        name = subentry.data[CONF_NAME]
        travel_time_id = subentry.data[CONF_ID]
        sensor = WashingtonStateTravelTimeSensor(
            name, wsdot_travel_times, travel_time_id
        )
        async_add_entities([sensor], config_subentry_id=subentry_id)


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
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
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
        self._attr_unique_id = f"Travel_Time_{travel_time_id}"

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
