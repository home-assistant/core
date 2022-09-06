"""Support for Rova garbage calendar."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from requests.exceptions import ConnectTimeout, HTTPError
from rova.rova import Rova
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import get_time_zone, now

# Config for rova requests.
CONF_ZIP_CODE = "zip_code"
CONF_HOUSE_NUMBER = "house_number"
CONF_HOUSE_NUMBER_SUFFIX = "house_number_suffix"

UPDATE_DELAY = timedelta(hours=12)
SCAN_INTERVAL = timedelta(hours=12)


SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "bio": SensorEntityDescription(
        key="gft",
        name="bio",
        icon="mdi:recycle",
    ),
    "paper": SensorEntityDescription(
        key="papier",
        name="paper",
        icon="mdi:recycle",
    ),
    "plastic": SensorEntityDescription(
        key="pmd",
        name="plastic",
        icon="mdi:recycle",
    ),
    "residual": SensorEntityDescription(
        key="restafval",
        name="residual",
        icon="mdi:recycle",
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ZIP_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_HOUSE_NUMBER_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_NAME, default="Rova"): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["bio"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the Rova data service and sensors."""

    zip_code = config[CONF_ZIP_CODE]
    house_number = config[CONF_HOUSE_NUMBER]
    house_number_suffix = config[CONF_HOUSE_NUMBER_SUFFIX]
    platform_name = config[CONF_NAME]

    # Create new Rova object to  retrieve data
    api = Rova(zip_code, house_number, house_number_suffix)

    try:
        if not api.is_rova_area():
            _LOGGER.error("ROVA does not collect garbage in this area")
            return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from ROVA API")
        return

    # Create rova data service which will retrieve and update the data.
    data_service = RovaData(api)

    # Create a new sensor for each garbage type.
    entities = [
        RovaSensor(platform_name, SENSOR_TYPES[sensor_key], data_service)
        for sensor_key in config[CONF_MONITORED_CONDITIONS]
    ]
    add_entities(entities, True)


class RovaSensor(SensorEntity):
    """Representation of a Rova sensor."""

    def __init__(
        self, platform_name, description: SensorEntityDescription, data_service
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self.data_service = data_service

        self._attr_name = f"{platform_name}_{description.name}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    def update(self) -> None:
        """Get the latest data from the sensor and update the state."""
        self.data_service.update()
        pickup_date = self.data_service.data.get(self.entity_description.key)
        if pickup_date is not None:
            self._attr_native_value = pickup_date


class RovaData:
    """Get and update the latest data from the Rova API."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.data = {}

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the Rova API."""

        try:
            items = self.api.get_calendar_items()
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, retry again later")
            return

        self.data = {}

        for item in items:
            date = datetime.strptime(item["Date"], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=get_time_zone("Europe/Amsterdam")
            )
            code = item["GarbageTypeCode"].lower()

            if code not in self.data and date > now():
                self.data[code] = date

        _LOGGER.debug("Updated Rova calendar: %s", self.data)
