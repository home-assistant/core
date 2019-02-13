"""
Schedules temperature updates to the climate component.

Schedule is read from 'schedule_persistance.json' in the
configuration directory.

Lovelace card to control it (WIP, in spanish):
https://gist.github.com/alex-torregrosa/482f62fec60d892b60b9dfe73289cd6f

Example component configuration:

climate_scheduler:
  target_climate: climate.home
"""
import json
import logging

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.util import dt
from homeassistant.helpers.event import (
    async_track_time_change)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.storage import Store


_LOGGER = logging.getLogger(__name__)

# The domain of your component. Equal to the filename of your component.
DOMAIN = "climate_scheduler"
ENTITY_ID = "climate_scheduler.main"
CONF_CLIMATE = 'target_climate'
ATTR_TIMES = "timetable"
DEFAULT_TIMES = "[]"
STORAGE_VERSION = 1
STORAGE_KEY = 'schedule_persistance'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIMATE): cv.entity_id,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Setups the climate scheduler component."""
    climate = config[DOMAIN].get(CONF_CLIMATE, None)
    if climate is None:
        _LOGGER.error("No climate provided.")
    ClimateScheduler(hass, climate)
    # Return boolean to indicate that initialization was successfully.
    return True


class ClimateScheduler(Entity):
    """Representation of a climate scheduler entity."""

    entity_id = ENTITY_ID

    def __init__(self, hass, climate):
        """Initialize the scheduler."""
        self.hass = hass
        self._state = STATE_ON
        self.climate = climate
        self.rules = []
        self.unsubs = []
        self.store = Store(hass, STORAGE_VERSION,
                           STORAGE_KEY)
        self.hass.loop.create_task(self.async_load_rules())

        hass.services.async_register(DOMAIN, 'update', self.handle_update)

    async def async_save_rules(self):
        """Save rules to storage."""
        await self.store.async_save(self.rules)

    async def async_load_rules(self):
        """Load rules from storage."""
        loaded_rules = await self.store.async_load()
        if loaded_rules is None:
            await self.async_save_rules()
        else:
            self.rules = loaded_rules
        self.update_rules()
        self.async_schedule_update_ha_state()

    def update_rules(self):
        """Update the trackers for all rules."""
        for unsub in self.unsubs:
            unsub()
        self.unsubs = []

        for rule_pos in range(len(self.rules)):
            rule = self.rules[rule_pos]
            r_time = tuple(map(int, rule['time'].split(':')))
            self.unsubs.append(
                async_track_time_change(self.hass,
                                        self.run_schecule(rule_pos),
                                        hour=r_time[0],
                                        minute=r_time[1],
                                        second=0))

    def run_schecule(self, rule_id):
        """Generate a callback function for the given rule."""
        @callback
        def run_id(now):
            temp = self.rules[rule_id]['temp']
            days = self.rules[rule_id]['days']
            if days[dt.as_local(now).weekday()]:
                self.hass.loop.create_task(
                    self.hass.services.async_call(
                        'climate',
                        'set_temperature',
                        {
                            "entity_id": self.climate,
                            "temperature": temp
                        }))
        return run_id

    @callback
    def handle_update(self, call):
        """Update the rule list."""
        new_rules = call.data.get(ATTR_TIMES, DEFAULT_TIMES)
        self.rules = json.loads(new_rules)
        self.hass.loop.create_task(self.async_save_rules())
        self.update_rules()
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Name of the device."""
        return 'Climate Scheduler'

    @property
    def state(self):
        """State of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        return {
            "rules_count": len(self.rules),
            "rules_json": json.dumps(self.rules)
        }
