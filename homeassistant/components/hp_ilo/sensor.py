"""Support for information from HP iLO sensors."""

from __future__ import annotations

from datetime import timedelta
import logging

import hpilo
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSOR_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HP ILO"
DEFAULT_PORT = 443

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

SENSOR_TYPES = {
    "server_name": ["Server Name", "get_server_name"],
    "server_fqdn": ["Server FQDN", "get_server_fqdn"],
    "server_host_data": ["Server Host Data", "get_host_data"],
    "server_oa_info": ["Server Onboard Administrator Info", "get_oa_info"],
    "server_power_status": ["Server Power state", "get_host_power_status"],
    "server_power_readings": ["Server Power readings", "get_power_readings"],
    "server_power_on_time": ["Server Power On time", "get_server_power_on_time"],
    "server_asset_tag": ["Server Asset Tag", "get_asset_tag"],
    "server_uid_status": ["Server UID light", "get_uid_status"],
    "server_health": ["Server Health", "get_embedded_health"],
    "network_settings": ["Network Settings", "get_network_settings"],
}

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_SENSOR_TYPE): vol.All(
                            cv.string, vol.In(SENSOR_TYPES)
                        ),
                        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
                    }
                )
            ],
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HP iLO sensors."""
    hostname = config[CONF_HOST]
    port = config[CONF_PORT]
    login = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    monitored_variables = config[CONF_MONITORED_VARIABLES]

    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data and confirm we can connect.
    try:
        hp_ilo_data = HpIloData(hostname, port, login, password)
    except ValueError as error:
        _LOGGER.error(error)
        return

    # Initialize and add all of the sensors.
    devices = []
    for monitored_variable in monitored_variables:
        new_device = HpIloSensor(
            hass=hass,
            hp_ilo_data=hp_ilo_data,
            sensor_name=f"{config[CONF_NAME]} {monitored_variable[CONF_NAME]}",
            sensor_type=monitored_variable[CONF_SENSOR_TYPE],
            sensor_value_template=monitored_variable.get(CONF_VALUE_TEMPLATE),
            unit_of_measurement=monitored_variable.get(CONF_UNIT_OF_MEASUREMENT),
        )
        devices.append(new_device)

    add_entities(devices, True)


class HpIloSensor(SensorEntity):
    """Representation of a HP iLO sensor."""

    def __init__(
        self,
        hass,
        hp_ilo_data,
        sensor_type,
        sensor_name,
        sensor_value_template,
        unit_of_measurement,
    ):
        """Initialize the HP iLO sensor."""
        self._hass = hass
        self._name = sensor_name
        self._unit_of_measurement = unit_of_measurement
        self._ilo_function = SENSOR_TYPES[sensor_type][1]
        self.hp_ilo_data = hp_ilo_data

        if sensor_value_template is not None:
            sensor_value_template.hass = hass
        self._sensor_value_template = sensor_value_template

        self._state = None
        self._state_attributes = None

        _LOGGER.debug("Created HP iLO sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._state_attributes

    def update(self) -> None:
        """Get the latest data from HP iLO and updates the states."""
        # Call the API for new data. Each sensor will re-trigger this
        # same exact call, but that's fine. Results should be cached for
        # a short period of time to prevent hitting API limits.
        self.hp_ilo_data.update()
        ilo_data = getattr(self.hp_ilo_data.data, self._ilo_function)()

        if self._sensor_value_template is not None:
            ilo_data = self._sensor_value_template.render(
                ilo_data=ilo_data, parse_result=False
            )

        self._state = ilo_data


class HpIloData:
    """Gets the latest data from HP iLO."""

    def __init__(self, host, port, login, password):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._login = login
        self._password = password

        self.data = None

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from HP iLO."""
        try:
            self.data = hpilo.Ilo(
                hostname=self._host,
                login=self._login,
                password=self._password,
                port=self._port,
            )
        except (
            hpilo.IloError,
            hpilo.IloCommunicationError,
            hpilo.IloLoginFailed,
        ) as error:
            raise ValueError(f"Unable to init HP ILO, {error}") from error
