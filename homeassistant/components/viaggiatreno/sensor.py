"""Support for the Italian train system using ViaggiaTreno API."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp
from viaggiatreno_ha.trainline import (
    TrainLine,
    TrainLineStatus,
    TrainState,
    Viaggiatreno,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:train"
MONITORED_INFO = [  # Backward compatibility with older versions
    "categoria",
    "compOrarioArrivoZeroEffettivo",
    "compOrarioPartenzaZeroEffettivo",
    "destinazione",
    "numeroTreno",
    "orarioArrivo",
    "orarioPartenza",
    "origine",
    "subTitle",
]

DEFAULT_NAME = "Train {}"

CONF_NAME = "train_name"
CONF_STATION_ID = "station_id"
CONF_TRAIN_ID = "train_id"

ARRIVED_STRING = "Arrived"
CANCELLED_STRING = "Cancelled"
NOT_DEPARTED_STRING = "Not departed yet"
NO_INFORMATION_STRING = "No information for this train now"

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TRAIN_ID): cv.string,
        vol.Required(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ViaggiaTreno platform."""
    train_id = str(config.get(CONF_TRAIN_ID))
    station_id = str(config.get(CONF_STATION_ID))
    if not (name := config.get(CONF_NAME)):
        name = DEFAULT_NAME.format(train_id)
    tl = TrainLine(train_id=train_id, starting_station=station_id)
    async_add_entities([ViaggiaTrenoSensor(tl, name)], True)


class ViaggiaTrenoSensor(SensorEntity):
    """Implementation of a ViaggiaTreno sensor."""

    _attr_attribution = "Powered by ViaggiaTreno Data"
    _attr_should_poll = True

    def __init__(self, train_line: TrainLine, name: str) -> None:
        """Initialize the sensor."""
        self._state: StateType = NO_INFORMATION_STRING
        self._attributes: dict[str, Any] = {}
        self._icon = ICON
        self._name = name
        self._line = train_line
        self._viaggiatreno: Viaggiatreno | None = None
        self._tstatus: TrainLineStatus | None = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if isinstance(self.native_value, (int, float)):
            return UnitOfTime.MINUTES
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return self._attributes

    async def async_update(self) -> None:
        """Update state."""
        if self._viaggiatreno is None:
            session = async_get_clientsession(self.hass)
            self._viaggiatreno = Viaggiatreno(session)
        try:
            await self._viaggiatreno.query_if_useful(self._line)
            self._tstatus = self._viaggiatreno.get_line_status(self._line)
            if self._tstatus is None:
                _LOGGER.error(
                    "Received status for line %s: None. Check the train and station IDs",
                    self._line,
                )
                return
        except (TimeoutError, aiohttp.ClientError) as exc:
            _LOGGER.error("Cannot connect to ViaggiaTreno API endpoint: %s", exc)
            return
        except ValueError:
            _LOGGER.error("Received non-JSON data from ViaggiaTreno API endpoint")
            return
        if self._tstatus is not None:
            if self._tstatus.state == TrainState.CANCELLED:
                self._state = CANCELLED_STRING
                self._icon = "mdi:cancel"
            elif self._tstatus.state == TrainState.NOT_YET_DEPARTED:
                self._state = NOT_DEPARTED_STRING
            elif self._tstatus.state == TrainState.ARRIVED:
                self._state = ARRIVED_STRING
            elif self._tstatus.state in {
                TrainState.RUNNING,
                TrainState.PARTIALLY_CANCELLED,
            }:
                delay_minutes = self._tstatus.timetable.delay
                self._state = delay_minutes
                self._icon = ICON
            else:
                self._state = NO_INFORMATION_STRING
            # Update attributes
            for info in MONITORED_INFO:
                self._attributes[info] = self._viaggiatreno.json[self._line][info]
