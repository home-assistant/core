"""
Support for Duke Energy Gas and Electric meters.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/duke_energy/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util as util

REQUIREMENTS = ['pydukeenergy==0.0.5']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    from pydukeenergy.api import DukeEnergy, DukeEnergyException

    try:
        duke = DukeEnergy(config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            update_interval=500)
    except DukeEnergyException:
        _LOGGER.error("Failed to setup Duke Energy")
        return False

    meters = duke.get_meters()
    sensors = []
    for meter in meters:
        sensors.append(DukeEnergyMeter(meter))
    add_devices(sensors)

    return True


class DukeEnergyMeter(Entity):
    """Representation of a Duke Energy meter."""

    def __init__(self, meter):
        """Initialize the meter."""
        self.duke_meter = meter

    @property
    def name(self):
        """Return the name."""
        return "duke_energy_" + self.duke_meter.id

    @property
    def state(self):
        """Return yesterdays usage."""
        return self.duke_meter.get_usage()

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self.duke_meter.get_unit()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "lastBillsUsage": self.duke_meter.get_total(),
            "lastBillsAverageUsage": self.duke_meter.get_average(),
            "lastBillsDaysBilled": self.duke_meter.get_days_billed()
        }
        return attributes

    def update(self):
        """Update meter."""
        self.duke_meter.update()

