"""Support for Start.ca Bandwidth Monitor."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from xml.parsers.expat import ExpatError

import async_timeout
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    DATA_GIGABYTES,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Start.ca"
CONF_TOTAL_BANDWIDTH = "total_bandwidth"

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
REQUEST_TIMEOUT = 5  # seconds

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="usage",
        name="Usage Ratio",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
    SensorEntityDescription(
        key="usage_gb",
        name="Usage",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="limit",
        name="Data limit",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="used_download",
        name="Used Download",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="used_upload",
        name="Used Upload",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="used_total",
        name="Used Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="grace_download",
        name="Grace Download",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="grace_upload",
        name="Grace Upload",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="grace_total",
        name="Grace Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="total_download",
        name="Total Download",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="total_upload",
        name="Total Upload",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="used_remaining",
        name="Remaining",
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TOTAL_BANDWIDTH): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    websession = async_get_clientsession(hass)
    apikey = config[CONF_API_KEY]
    bandwidthcap = config[CONF_TOTAL_BANDWIDTH]

    ts_data = StartcaData(hass.loop, websession, apikey, bandwidthcap)
    ret = await ts_data.async_update()
    if ret is False:
        _LOGGER.error("Invalid Start.ca API key: %s", apikey)
        return

    name = config[CONF_NAME]
    monitored_variables = config[CONF_MONITORED_VARIABLES]
    entities = [
        StartcaSensor(ts_data, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]
    async_add_entities(entities, True)


class StartcaSensor(SensorEntity):
    """Representation of Start.ca Bandwidth sensor."""

    def __init__(self, startcadata, name, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.startcadata = startcadata

        self._attr_name = f"{name} {description.name}"

    async def async_update(self):
        """Get the latest data from Start.ca and update the state."""
        await self.startcadata.async_update()
        sensor_type = self.entity_description.key
        if sensor_type in self.startcadata.data:
            self._attr_native_value = round(self.startcadata.data[sensor_type], 2)


class StartcaData:
    """Get data from Start.ca API."""

    def __init__(self, loop, websession, api_key, bandwidth_cap):
        """Initialize the data object."""
        self.loop = loop
        self.websession = websession
        self.api_key = api_key
        self.bandwidth_cap = bandwidth_cap
        # Set unlimited users to infinite, otherwise the cap.
        self.data = (
            {"limit": self.bandwidth_cap}
            if self.bandwidth_cap > 0
            else {"limit": float("inf")}
        )

    @staticmethod
    def bytes_to_gb(value):
        """Convert from bytes to GB.

        :param value: The value in bytes to convert to GB.
        :return: Converted GB value
        """
        return float(value) * 10**-9

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the Start.ca bandwidth data from the web service."""
        _LOGGER.debug("Updating Start.ca usage data")
        url = f"https://www.start.ca/support/usage/api?key={self.api_key}"
        async with async_timeout.timeout(REQUEST_TIMEOUT):
            req = await self.websession.get(url)
        if req.status != HTTPStatus.OK:
            _LOGGER.error("Request failed with status: %u", req.status)
            return False

        data = await req.text()
        try:
            xml_data = xmltodict.parse(data)
        except ExpatError:
            return False

        used_dl = self.bytes_to_gb(xml_data["usage"]["used"]["download"])
        used_ul = self.bytes_to_gb(xml_data["usage"]["used"]["upload"])
        grace_dl = self.bytes_to_gb(xml_data["usage"]["grace"]["download"])
        grace_ul = self.bytes_to_gb(xml_data["usage"]["grace"]["upload"])
        total_dl = self.bytes_to_gb(xml_data["usage"]["total"]["download"])
        total_ul = self.bytes_to_gb(xml_data["usage"]["total"]["upload"])

        limit = self.data["limit"]
        if self.bandwidth_cap > 0:
            self.data["usage"] = 100 * used_dl / self.bandwidth_cap
        else:
            self.data["usage"] = 0
        self.data["usage_gb"] = used_dl
        self.data["used_download"] = used_dl
        self.data["used_upload"] = used_ul
        self.data["used_total"] = used_dl + used_ul
        self.data["grace_download"] = grace_dl
        self.data["grace_upload"] = grace_ul
        self.data["grace_total"] = grace_dl + grace_ul
        self.data["total_download"] = total_dl
        self.data["total_upload"] = total_ul
        self.data["used_remaining"] = limit - used_dl

        return True
