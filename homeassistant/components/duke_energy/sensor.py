"""Support for Duke Energy Gas and Electric meters."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

LAST_BILL_USAGE = "last_bills_usage"
LAST_BILL_AVERAGE_USAGE = "last_bills_average_usage"
LAST_BILL_DAYS_BILLED = "last_bills_days_billed"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up all Duke Energy meters."""
    from pydukeenergy.api import DukeEnergy, DukeEnergyException

    try:
        duke = DukeEnergy(config[CONF_USERNAME],
                          config[CONF_PASSWORD],
                          update_interval=120)
    except DukeEnergyException:
        _LOGGER.error("Failed to set up Duke Energy")
        return

    add_entities([DukeEnergyMeter(meter) for meter in duke.get_meters()])


class DukeEnergyMeter(Entity):
    """Representation of a Duke Energy meter."""

    def __init__(self, meter):
        """Initialize the meter."""
        self.duke_meter = meter

    @property
    def name(self):
        """Return the name."""
        return "duke_energy_{}".format(self.duke_meter.id)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self.duke_meter.id

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
            LAST_BILL_USAGE: self.duke_meter.get_total(),
            LAST_BILL_AVERAGE_USAGE: self.duke_meter.get_average(),
            LAST_BILL_DAYS_BILLED: self.duke_meter.get_days_billed()
        }
        return attributes

    def update(self):
        """Update meter."""
        self.duke_meter.update()
