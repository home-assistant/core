"""Support for Efergy sensors."""
from __future__ import annotations

import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_CURRENCY,
    CONF_MONITORED_VARIABLES,
    CONF_TYPE,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://engage.efergy.com/mobile_proxy/"

CONF_APPTOKEN = "app_token"
CONF_UTC_OFFSET = "utc_offset"

CONF_PERIOD = "period"

CONF_INSTANT = "instant_readings"
CONF_AMOUNT = "amount"
CONF_BUDGET = "budget"
CONF_COST = "cost"
CONF_CURRENT_VALUES = "current_values"

DEFAULT_PERIOD = "year"
DEFAULT_UTC_OFFSET = "0"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONF_INSTANT,
        name="Energy Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=CONF_AMOUNT,
        name="Energy Consumed",
        device_class=DEVICE_CLASS_ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=CONF_BUDGET,
        name="Energy Budget",
    ),
    SensorEntityDescription(
        key=CONF_COST,
        name="Energy Cost",
    ),
    SensorEntityDescription(
        key=CONF_CURRENT_VALUES,
        name="Per-Device Usage",
        device_class=DEVICE_CLASS_POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

TYPES_SCHEMA = vol.In(SENSOR_TYPES)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): TYPES_SCHEMA,
        vol.Optional(CONF_CURRENCY, default=""): cv.string,
        vol.Optional(CONF_PERIOD, default=DEFAULT_PERIOD): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APPTOKEN): cv.string,
        vol.Optional(CONF_UTC_OFFSET, default=DEFAULT_UTC_OFFSET): cv.string,
        vol.Required(CONF_MONITORED_VARIABLES): [SENSORS_SCHEMA],
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Efergy sensor."""
    app_token = config.get(CONF_APPTOKEN)
    utc_offset = str(config.get(CONF_UTC_OFFSET))

    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        for description in SENSOR_TYPES:
            if variable[CONF_TYPE] == description.key:
                if (
                    description.key == CONF_CURRENT_VALUES
                    and description.key in config[CONF_MONITORED_VARIABLES]
                ):
                    url_string = f"{_RESOURCE}getCurrentValuesSummary?token={app_token}"
                    response = requests.get(url_string, timeout=10)
                    for sensor in response.json():
                        sid = sensor["sid"]
                        dev.append(
                            EfergySensor(
                                app_token,
                                utc_offset,
                                variable[CONF_PERIOD],
                                variable[CONF_CURRENCY],
                                description,
                                sid,
                            )
                        )
                dev.append(
                    EfergySensor(
                        app_token,
                        utc_offset,
                        variable[CONF_PERIOD],
                        variable[CONF_CURRENCY],
                        description,
                    )
                )

    add_entities(dev, True)


class EfergySensor(SensorEntity):
    """Implementation of an Efergy sensor."""

    def __init__(
        self,
        app_token,
        utc_offset,
        period,
        currency,
        description: SensorEntityDescription,
        sid=None,
    ):
        """Initialize the sensor."""
        self.sid = sid
        if sid:
            self._attr_name = f"efergy_{sid}"
        else:
            self._attr_name = description.name
        self.type = description.key
        self.app_token = app_token
        self.utc_offset = utc_offset
        self.period = period
        if description.key == CONF_COST:
            self._attr_native_unit_of_measurement = f"{currency}/{period}"
        else:
            self._attr_native_unit_of_measurement = (
                description.native_unit_of_measurement
            )
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    def update(self):
        """Get the Efergy monitor data from the web service."""
        try:
            if self.type == CONF_INSTANT:
                url_string = f"{_RESOURCE}getInstant?token={self.app_token}"
                response = requests.get(url_string, timeout=10)
                self._attr_native_value = response.json()["reading"]
            elif self.type == CONF_AMOUNT:
                url_string = f"{_RESOURCE}getEnergy?token={self.app_token}&offset={self.utc_offset}&period={self.period}"
                response = requests.get(url_string, timeout=10)
                self._attr_native_value = response.json()["sum"]
            elif self.type == CONF_BUDGET:
                url_string = f"{_RESOURCE}getBudget?token={self.app_token}"
                response = requests.get(url_string, timeout=10)
                self._attr_native_value = response.json()["status"]
            elif self.type == CONF_COST:
                url_string = f"{_RESOURCE}getCost?token={self.app_token}&offset={self.utc_offset}&period={self.period}"
                response = requests.get(url_string, timeout=10)
                self._attr_native_value = response.json()["sum"]
            elif self.type == CONF_CURRENT_VALUES:
                url_string = (
                    f"{_RESOURCE}getCurrentValuesSummary?token={self.app_token}"
                )
                response = requests.get(url_string, timeout=10)
                for sensor in response.json():
                    if self.sid == sensor["sid"]:
                        measurement = next(iter(sensor["data"][0].values()))
                        self._attr_native_value = measurement
            else:
                self._attr_native_value = None
        except (requests.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
