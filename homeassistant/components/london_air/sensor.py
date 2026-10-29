"""Sensor for checking the status of London air."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

import probatio
from pylondonair import (
    NO_SPECIES_DATA,
    LondonAirClient,
    LondonAirConnectionError,
    LondonAirData,
    LondonAirUpdateError,
    Site,
)

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_LOCATIONS = "locations"

SCAN_INTERVAL = timedelta(minutes=30)

AUTHORITIES = [
    "Barking and Dagenham",
    "Barnet",
    "Bexley",
    "Brent",
    "Bromley",
    "Camden",
    "City of London",
    "Croydon",
    "Ealing",
    "Enfield",
    "Greenwich",
    "Hackney",
    "Hammersmith and Fulham",
    "Haringey",
    "Harrow",
    "Havering",
    "Hillingdon",
    "Hounslow",
    "Islington",
    "Kensington and Chelsea",
    "Kingston",
    "Lambeth",
    "Lewisham",
    "Merton",
    "Newham",
    "Redbridge",
    "Richmond",
    "Southwark",
    "Sutton",
    "Tower Hamlets",
    "Waltham Forest",
    "Wandsworth",
    "Westminster",
]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_LOCATIONS, default=AUTHORITIES): probatio.All(
            probatio.EnsureList(), [probatio.In(AUTHORITIES)]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the London Air sensor."""
    data = APIData(hass)
    await data.async_update()

    async_add_entities((AirSensor(name, data) for name in config[CONF_LOCATIONS]), True)


class APIData:
    """Get the latest data for all authorities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the AirData object."""
        self._client = LondonAirClient(session=async_get_clientsession(hass))
        self.data: LondonAirData | None = None
        self._last_update: datetime | None = None

    async def async_update(self) -> None:
        """Get the latest data from the API, at most once per scan interval."""
        now = dt_util.utcnow()
        if self._last_update is not None and now - self._last_update <= SCAN_INTERVAL:
            return
        self._last_update = now
        try:
            self.data = await self._client.async_update()
        except LondonAirConnectionError as err:
            _LOGGER.warning("Could not connect to London Air API: %s", err)
        except LondonAirUpdateError as err:
            _LOGGER.warning("Invalid response from London Air API: %s", err)


class AirSensor(SensorEntity):
    """Single authority air sensor."""

    _attr_icon = "mdi:cloud-outline"

    def __init__(self, name: str, api_data: APIData) -> None:
        """Initialize the sensor."""
        self._attr_name = self._key = name
        self._api_data = api_data
        self._site_data: list[dict[str, Any]] | None = None
        self._updated: str | None = None

    @property
    def site_data(self) -> list[dict[str, Any]] | None:
        """Return the dict of sites data."""
        return self._site_data

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details about the sensor state."""
        attrs: dict[str, Any] = {}
        attrs["updated"] = self._updated
        attrs["sites"] = len(self._site_data) if self._site_data is not None else 0
        attrs["data"] = self._site_data
        return attrs

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._api_data.async_update()
        data = self._api_data.data
        if data is None:
            self._attr_native_value = None
            return
        authority = data.authorities.get(self._key)
        sites = authority.sites if authority is not None else ()
        self._site_data = [_site_to_dict(site) for site in sites]
        self._updated = (
            sites[0].updated.strftime("%Y-%m-%d %H:%M:%S") if sites else None
        )
        self._attr_native_value = authority.status if authority is not None else None


def _site_to_dict(site: Site) -> dict[str, Any]:
    """Convert a library site into the attribute dict format."""
    pollutants: list[dict[str, str] | str] = [
        {
            "description": pollutant.description,
            "code": pollutant.code,
            "quality": pollutant.quality,
            "index": pollutant.index,
            "summary": pollutant.summary,
        }
        for pollutant in site.pollutants
    ]
    if not pollutants:
        pollutants = [NO_SPECIES_DATA]
    return {
        "updated": site.updated.strftime("%Y-%m-%d %H:%M:%S"),
        "latitude": site.latitude,
        "longitude": site.longitude,
        "site_code": site.site_code,
        "site_name": site.site_name,
        "site_type": site.site_type,
        "pollutants": pollutants,
        "pollutants_status": site.status,
        "number_of_pollutants": site.number_of_pollutants,
    }
