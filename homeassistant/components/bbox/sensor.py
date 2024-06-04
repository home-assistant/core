"""Support for Bbox Bouygues Modem Router."""

from __future__ import annotations

from datetime import timedelta
import logging

import pybbox
import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_MONITORED_VARIABLES, CONF_NAME, UnitOfDataRate
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
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
        bbox_data = BboxData()
        bbox_data.update()
    except requests.exceptions.HTTPError as error:
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

    def __init__(self) -> None:
        """Initialize the data object."""
        self.data = None
        self.router_infos = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Bbox."""

        try:
            box = pybbox.Bbox()
            self.data = box.get_ip_stats()
            self.router_infos = box.get_bbox_info()
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(error)
            self.data = None
            self.router_infos = None
            return False
