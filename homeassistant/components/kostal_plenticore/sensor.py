"""Kostal Plenticore Inverter."""
import logging

import kostalplenticore
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

"""Platform for sensor integration."""

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "BatteryPercent": [
        "devices:local:battery",
        "SoC",
        "Kostal Battery",
        "%",
        "mdi:battery-high",
    ],
    "BatteryCycles": [
        "devices:local:battery",
        "Cycles",
        "Kostal Battery Cycles",
        None,
        "mdi:recycle-variant",
    ],
    "HomeOwnPower": [
        "devices:local",
        "HomeOwn_P",
        "Kostal home power",
        "W",
        "mdi:home",
    ],
    "HomePVPower": [
        "devices:local",
        "HomePv_P",
        "Kostal home power from PV",
        "W",
        "mdi:solar-power",
    ],
    "HomeBatteryPower": [
        "devices:local",
        "HomeBat_P",
        "Kostal home power from Battery",
        "W",
        "mdi:battery-charging-90",
    ],
    "HomeGridPower": [
        "devices:local",
        "HomeGrid_P",
        "Kostal home power from Grid",
        "W",
        "mdi:transmission-tower",
    ],
    "PVPower": ["devices:local", "Dc_P", "Kostal pv power", "W", "mdi:solar-power"],
    "AutarkyDay": [
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Day",
        "Kostal autarky day",
        "%",
        "mdi:power-plug",
    ],
    "AutarkyMonth": [
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Month",
        "Kostal autarky Month",
        "%",
        "mdi:power-plug",
    ],
    "AutarkyTotal": [
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Total",
        "Kostal autarky Total",
        "%",
        "mdi:power-plug",
    ],
    "AutarkyYear": [
        "scb:statistic:EnergyFlow",
        "Statistic:Autarky:Year",
        "Kostal autarky Year",
        "%",
        "mdi:power-plug",
    ],
    "CO2SavingDay": [
        "scb:statistic:EnergyFlow",
        "Statistic:CO2Saving:Day",
        "Kostal CO2 Saving Day",
        "kg",
        "mdi:molecule-co2",
    ],
    "CO2SavingMonth": [
        "scb:statistic:EnergyFlow",
        "Statistic:CO2Saving:Month",
        "Kostal CO2 Saving Month",
        "kg",
        "mdi:molecule-co2",
    ],
    "CO2SavingTotal": [
        "scb:statistic:EnergyFlow",
        "Statistic:CO2Saving:Total",
        "Kostal CO2 Saving Total",
        "kg",
        "mdi:molecule-co2",
    ],
    "CO2SavingYear": [
        "scb:statistic:EnergyFlow",
        "Statistic:CO2Saving:Year",
        "Kostal CO2 Saving Year",
        "kg",
        "mdi:molecule-co2",
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    host = config[CONF_HOST]
    password = config[CONF_PASSWORD]
    monitoredcondition = config[CONF_MONITORED_CONDITIONS]

    """ Login to Kostal Plenticore """
    con = kostalplenticore.connect(host, password)
    con.login()

    for sensor in monitoredcondition:
        add_entities(
            [
                plenticore(
                    con,
                    SENSOR_TYPES[sensor][2],
                    SENSOR_TYPES[sensor][0],
                    SENSOR_TYPES[sensor][1],
                    SENSOR_TYPES[sensor][3],
                    SENSOR_TYPES[sensor][4],
                )
            ]
        )


class plenticore(Entity):
    """Representation of a Sensor."""

    def __init__(self, con, sensorname, moduleid, id, unit, icon):
        """Initialize the sensor."""
        self.api = con
        self.sensorname = sensorname
        self.moduleid = moduleid
        self.id = id
        self.mdi = icon
        self.unit = unit
        self._state = int(self.api.getProcessdata(self.moduleid, [self.id])[0]["value"])

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.sensorname

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.mdi

    @property
    def state(self):
        """Return State."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        # self._state = 23
        self._state = int(self.api.getProcessdata(self.moduleid, [self.id])[0]["value"])
