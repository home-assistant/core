"""Support for the NOAA Tides and Currents API."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import noaa_coops as coops
import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE, CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONF_STATION_ID,
    DEFAULT_TIMEZONE,
    DOMAIN,
    NAME,
    TIMEZONES,
    UNIT_SYSTEMS,
)
from .errors import StationNotFound
from .helpers import get_default_unit_system, get_station_unique_id

if TYPE_CHECKING:
    from pandas import Timestamp

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NOAA Tides"

SCAN_INTERVAL = timedelta(minutes=60)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIME_ZONE, default=DEFAULT_TIMEZONE): vol.In(TIMEZONES),
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNIT_SYSTEMS),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NOAA Tides and Currents sensor."""
    station_id = config[CONF_STATION_ID]
    name = config.get(CONF_NAME)
    timezone = config.get(CONF_TIME_ZONE)

    if CONF_UNIT_SYSTEM in config:
        unit_system = config[CONF_UNIT_SYSTEM]
    elif hass.config.units is METRIC_SYSTEM:
        unit_system = UNIT_SYSTEMS[1]
    else:
        unit_system = UNIT_SYSTEMS[0]

    try:
        station = coops.Station(station_id, unit_system)
    except KeyError:
        _LOGGER.error("NOAA Tides Sensor station_id %s does not exist", station_id)
        return
    except requests.exceptions.ConnectionError as exception:
        _LOGGER.error(
            "Connection error during setup in NOAA Tides Sensor for station_id: %s",
            station_id,
        )
        raise PlatformNotReady from exception

    noaa_sensor = NOAATidesAndCurrentsSensor(
        name, station_id, timezone, unit_system, station
    )

    add_entities([noaa_sensor], True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add NOAA Tides sensor entry."""

    station_id = entry.data.get(CONF_STATION_ID)
    name = entry.title
    timezone = entry.options.get(CONF_TIME_ZONE, DEFAULT_TIMEZONE)
    unit_system = entry.options.get(CONF_UNIT_SYSTEM, get_default_unit_system(hass))

    if station_id is None:
        _LOGGER.error("Station ID is required")
        raise StationNotFound

    try:
        station = await hass.async_add_executor_job(
            coops.Station, station_id, unit_system
        )
    except KeyError as exception:
        _LOGGER.error("%s sensor station_id %s does not exist", NAME, station_id)
        raise StationNotFound from exception
    except requests.exceptions.ConnectionError as exception:
        _LOGGER.error(
            "Connection error during setup in %s sensor for station_id: %s",
            NAME,
            station_id,
        )
        raise PlatformNotReady from exception

    device_id = get_station_unique_id(station_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=name,
        entry_type=DeviceEntryType.SERVICE,
    )

    summary_sensor = NOAATidesAndCurrentsSensor(
        name, station_id, timezone, unit_system, station, device_info=device_info
    )

    async_add_entities([summary_sensor], True)


class NOAATidesData(TypedDict):
    """Representation of a single tide."""

    time_stamp: list[Timestamp]
    hi_lo: list[Literal["L", "H"]]
    predicted_wl: list[float]


class NOAATidesAndCurrentsSensor(SensorEntity):
    """Representation of a NOAA Tides and Currents sensor."""

    _attr_attribution = "Data provided by NOAA"

    def __init__(
        self,
        name: str | None,
        station_id: str,
        timezone: str | None,
        unit_system: str,
        station: coops.Station,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._name = name if name is not None else DEFAULT_NAME
        self._station_id = station_id
        self._timezone = timezone if timezone is not None else DEFAULT_TIMEZONE
        self._unit_system = unit_system
        self._station = station
        self.data: NOAATidesData | None = None
        self._attr_unique_id = f"{get_station_unique_id(station_id)}_summary"
        self._attr_device_info = device_info

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this device."""
        attr: dict[str, Any] = {}
        if self.data is None:
            return attr
        if self.data["hi_lo"][1] == "H":
            attr["high_tide_time"] = self.data["time_stamp"][1].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["high_tide_height"] = self.data["predicted_wl"][1]
            attr["low_tide_time"] = self.data["time_stamp"][2].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["low_tide_height"] = self.data["predicted_wl"][2]
        elif self.data["hi_lo"][1] == "L":
            attr["low_tide_time"] = self.data["time_stamp"][1].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["low_tide_height"] = self.data["predicted_wl"][1]
            attr["high_tide_time"] = self.data["time_stamp"][2].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["high_tide_height"] = self.data["predicted_wl"][2]
        return attr

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.data is None:
            return None
        api_time = self.data["time_stamp"][0]
        if self.data["hi_lo"][0] == "H":
            tidetime = api_time.strftime("%-I:%M %p")
            return f"High tide at {tidetime}"
        if self.data["hi_lo"][0] == "L":
            tidetime = api_time.strftime("%-I:%M %p")
            return f"Low tide at {tidetime}"
        return None

    def update(self) -> None:
        """Get the latest data from NOAA Tides and Currents API."""
        begin = datetime.now()
        delta = timedelta(days=2)
        end = begin + delta
        try:
            df_predictions = self._station.get_data(
                begin_date=begin.strftime("%Y%m%d %H:%M"),
                end_date=end.strftime("%Y%m%d %H:%M"),
                product="predictions",
                datum="MLLW",
                interval="hilo",
                units=self._unit_system,
                time_zone=self._timezone,
            )
            api_data = df_predictions.head()
            self.data = NOAATidesData(
                time_stamp=list(api_data.index),
                hi_lo=list(api_data["type"].values),
                predicted_wl=list(api_data["v"].values),
            )
            _LOGGER.debug("Data = %s", api_data)
            _LOGGER.debug(
                "Recent Tide data queried with start time set to %s",
                begin.strftime("%m-%d-%Y %H:%M"),
            )
        except ValueError as err:
            _LOGGER.error("Check %s and Currents: %s", NAME, err.args)
            self.data = None
