"""Support for Bbox Bouygues Modem Router."""

from asyncio import run_coroutine_threadsafe
from datetime import timedelta
import logging

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

from .api import BboxApi, BboxError
from .const import DEFAULT_HOST, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by Bouygues Telecom"

DEFAULT_NAME = "Bbox"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="down_max_bandwidth",
        name="Maximum Download Bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="up_max_bandwidth",
        name="Maximum Upload Bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="current_down_bandwidth",
        name="Currently Used Download Bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="current_up_bandwidth",
        name="Currently Used Upload Bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="number_of_reboots",
        name="Number of reboot",
        icon="mdi:restart",
    ),
)

SENSOR_TYPES_UPTIME: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:clock",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in (*SENSOR_TYPES, *SENSOR_TYPES_UPTIME)]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_MONITORED_VARIABLES): probatio.All(
            probatio.EnsureList(), [probatio.In(SENSOR_KEYS)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        # The Bbox only needs the password for endpoints like the hosts
        # list; the WAN and device endpoints answer without it.
        probatio.Optional(CONF_PASSWORD, default=""): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bbox sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.
    try:
        bbox_data = BboxData(hass, config[CONF_HOST], config[CONF_PASSWORD])
        bbox_data.update()
    except BboxError as error:
        _LOGGER.error(error)
        return

    name = config[CONF_NAME]

    monitored_variables = config[CONF_MONITORED_VARIABLES]
    entities: list[BboxSensor | BboxUptimeSensor] = [
        BboxSensor(bbox_data, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_variables
    ]
    entities.extend(
        [
            BboxUptimeSensor(bbox_data, name, description)
            for description in SENSOR_TYPES_UPTIME
            if description.key in monitored_variables
        ]
    )

    add_entities(entities, True)


class BboxUptimeSensor(SensorEntity):
    """Bbox uptime sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, bbox_data, name, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self.bbox_data = bbox_data

    def update(self) -> None:
        """Get the latest data from Bbox and update the state."""
        self.bbox_data.update()
        self._attr_native_value = utcnow() - timedelta(
            seconds=self.bbox_data.router_infos["device"]["uptime"]
        )


class BboxSensor(SensorEntity):
    """Implementation of a Bbox sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, bbox_data, name, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self.bbox_data = bbox_data

    def update(self) -> None:
        """Get the latest data from Bbox and update the state."""
        self.bbox_data.update()
        sensor_type = self.entity_description.key
        if sensor_type == "down_max_bandwidth":
            self._attr_native_value = round(
                self.bbox_data.data["rx"]["maxBandwidth"] / 1000, 2
            )
        elif sensor_type == "up_max_bandwidth":
            self._attr_native_value = round(
                self.bbox_data.data["tx"]["maxBandwidth"] / 1000, 2
            )
        elif sensor_type == "current_down_bandwidth":
            self._attr_native_value = round(
                self.bbox_data.data["rx"]["bandwidth"] / 1000, 2
            )
        elif sensor_type == "current_up_bandwidth":
            self._attr_native_value = round(
                self.bbox_data.data["tx"]["bandwidth"] / 1000, 2
            )
        elif sensor_type == "number_of_reboots":
            self._attr_native_value = self.bbox_data.router_infos["device"][
                "numberofboots"
            ]


class BboxData:
    """Get data from the Bbox."""

    def __init__(self, hass: HomeAssistant, host: str, password: str | None) -> None:
        """Initialize the data object."""
        self._hass = hass
        self._host = host
        self._password = password
        self._api: BboxApi | None = None
        self.data = None
        self.router_infos = None

    async def _async_fetch(self):
        """Fetch the stats and the device info from the event loop.

        The session and the api client must be created on the event loop:
        this method only runs there, through the bridge in :meth:`update`.
        """
        if self._api is None:
            self._api = BboxApi(
                async_get_clientsession(self._hass), self._password, self._host
            )
        return await self._api.get_ip_stats_and_info()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Bbox."""

        future = None
        try:
            future = run_coroutine_threadsafe(self._async_fetch(), self._hass.loop)
            self.data, self.router_infos = future.result(REQUEST_TIMEOUT)
        except (BboxError, TimeoutError) as error:
            # Do not leave the abandoned fetch running under a bridge
            # timeout: it would keep hitting the Bbox for a discarded
            # result.
            if future is not None:
                future.cancel()
            _LOGGER.error(error)
            self.data = None
            self.router_infos = None
            return False
