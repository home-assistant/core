"""Support for EBox.

Get data from 'My Usage Page' page: https://client.ebox.ca/myusage
"""
from __future__ import annotations

from datetime import timedelta
import logging

from pyebox import EboxClient
from pyebox.client import PyEboxError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    PERCENTAGE,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

PRICE = "CAD"

DEFAULT_NAME = "EBox"

REQUESTS_TIMEOUT = 15
SCAN_INTERVAL = timedelta(minutes=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="usage",
        name="Usage",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
    SensorEntityDescription(
        key="balance",
        name="Balance",
        native_unit_of_measurement=PRICE,
        icon="mdi:cash",
    ),
    SensorEntityDescription(
        key="limit",
        name="Data limit",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="days_left",
        name="Days left",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-today",
    ),
    SensorEntityDescription(
        key="before_offpeak_download",
        name="Download before offpeak",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="before_offpeak_upload",
        name="Upload before offpeak",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="before_offpeak_total",
        name="Total before offpeak",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="offpeak_download",
        name="Offpeak download",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="offpeak_upload",
        name="Offpeak Upload",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="offpeak_total",
        name="Offpeak Total",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="download",
        name="Download",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="upload",
        name="Upload",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="total",
        name="Total",
        native_unit_of_measurement=UnitOfInformation.GIGABITS,
        device_class=SensorDeviceClass.DATA_SIZE,
        icon="mdi:download",
    ),
)

SENSOR_TYPE_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPE_KEYS)]
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EBox sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    httpsession = async_get_clientsession(hass)
    ebox_data = EBoxData(username, password, httpsession)

    name = config.get(CONF_NAME)

    try:
        await ebox_data.async_update()
    except PyEboxError as exp:
        _LOGGER.error("Failed login: %s", exp)
        raise PlatformNotReady from exp

    sensors = [
        EBoxSensor(ebox_data, description, name)
        for description in SENSOR_TYPES
        if description.key in config[CONF_MONITORED_VARIABLES]
    ]

    async_add_entities(sensors, True)


class EBoxSensor(SensorEntity):
    """Implementation of a EBox sensor."""

    def __init__(
        self,
        ebox_data,
        description: SensorEntityDescription,
        name,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self.ebox_data = ebox_data

    async def async_update(self) -> None:
        """Get the latest data from EBox and update the state."""
        await self.ebox_data.async_update()
        if self.entity_description.key in self.ebox_data.data:
            self._attr_native_value = round(
                self.ebox_data.data[self.entity_description.key], 2
            )


class EBoxData:
    """Get data from Ebox."""

    def __init__(self, username, password, httpsession):
        """Initialize the data object."""
        self.client = EboxClient(username, password, REQUESTS_TIMEOUT, httpsession)
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Ebox."""
        try:
            await self.client.fetch_data()
        except PyEboxError as exp:
            _LOGGER.error("Error on receive last EBox data: %s", exp)
            return
        # Update data
        self.data = self.client.get_data()
