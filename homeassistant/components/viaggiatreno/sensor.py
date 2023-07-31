"""Support for the Italian train system using ViaggiaTreno API."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
import time

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

VIAGGIATRENO_ENDPOINT = (
    "http://www.viaggiatreno.it/infomobilita/"
    "resteasy/viaggiatreno/andamentoTreno/"
    "{station_id}/{train_id}/{timestamp}"
)

REQUEST_TIMEOUT = 5  # seconds
ICON = "mdi:train"
MONITORED_INFO = [
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
CONF_STATION_NAME = "station_name"
CONF_TRAIN_ID = "train_id"

ARRIVED_STRING = "Arrived"
CANCELLED_STRING = "Cancelled"
NOT_DEPARTED_STRING = "Not departed yet"
NO_INFORMATION_STRING = "No information for this train now"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
    train_id = config.get(CONF_TRAIN_ID)
    station_id = config.get(CONF_STATION_ID)
    if not (name := config.get(CONF_NAME)):
        name = DEFAULT_NAME.format(train_id)
    async_add_entities([ViaggiaTrenoSensor(train_id, station_id, name)])


async def async_http_request(hass, uri):
    """Perform actual request."""
    try:
        session = async_get_clientsession(hass)
        async with async_timeout.timeout(REQUEST_TIMEOUT):
            req = await session.get(uri)
        if req.status != HTTPStatus.OK:
            return {"error": req.status}
        json_response = await req.json()
        return json_response
    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        _LOGGER.error("Cannot connect to ViaggiaTreno API endpoint: %s", exc)
    except ValueError:
        _LOGGER.error("Received non-JSON data from ViaggiaTreno API endpoint")


class ViaggiaTrenoSensor(SensorEntity):
    """Implementation of a ViaggiaTreno sensor."""

    _attr_attribution = "Powered by ViaggiaTreno Data"

    def __init__(self, train_id, station_id, name):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self._unit = ""
        self._icon = ICON
        self._station_id = station_id
        self._name = name

        self.uri = VIAGGIATRENO_ENDPOINT.format(
            station_id=station_id, train_id=train_id, timestamp=int(time.time()) * 1000
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return self._attributes

    @staticmethod
    def has_departed(data):
        """Check if the train has actually departed."""
        try:
            first_station = data["fermate"][0]
            if data["oraUltimoRilevamento"] or first_station["effettiva"]:
                return True
        except ValueError:
            _LOGGER.error("Cannot fetch first station: %s", data)
        return False

    @staticmethod
    def has_arrived(data):
        """Check if the train has already arrived."""
        last_station = data["fermate"][-1]
        if not last_station["effettiva"]:
            return False
        return True

    @staticmethod
    def is_cancelled(data):
        """Check if the train is cancelled."""
        if data["tipoTreno"] == "ST" and data["provvedimento"] == 1:
            return True
        return False

    async def async_update(self) -> None:
        """Update state."""
        uri = self.uri
        res = await async_http_request(self.hass, uri)
        if res.get("error", ""):
            if res["error"] == 204:
                self._state = NO_INFORMATION_STRING
                self._unit = ""
            else:
                self._state = "Error: {}".format(res["error"])
                self._unit = ""
        else:
            for i in MONITORED_INFO:
                self._attributes[i] = res[i]

            if self.is_cancelled(res):
                self._state = CANCELLED_STRING
                self._icon = "mdi:cancel"
                self._unit = ""
            elif not self.has_departed(res):
                self._state = NOT_DEPARTED_STRING
                self._unit = ""
            elif self.has_arrived(res):
                self._state = ARRIVED_STRING
                self._unit = ""
            else:
                self._state = res.get("ritardo")
                self._unit = UnitOfTime.MINUTES
                self._icon = ICON
