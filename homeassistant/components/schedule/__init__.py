"""
Schedules temperature updates to components.

Example component configuration:

schedule:
  entities:
    -climate.home
"""
import json
import logging

import voluptuous as vol

from homeassistant.helpers.event import async_track_state_change
from homeassistant.util import dt
from homeassistant.helpers.event import (
    async_track_time_change)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import callback, split_entity_id
from homeassistant.helpers.storage import Store
from homeassistant.components import websocket_api


_LOGGER = logging.getLogger(__name__)

DOMAIN = "schedule"

STORAGE_VERSION = 1
STORAGE_KEY = 'schedule'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ENTITIES): cv.comp_entity_ids,
    })
}, extra=vol.ALLOW_EXTRA)


WS_TYPE_SCHEDULE_RULES = 'schedule/rules'
SCHEMA_WEBSOCKET_GET_RULES = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        'type': WS_TYPE_SCHEDULE_RULES
    })

WS_TYPE_SCHEDULE_ENTITIES = 'schedule/entities'
SCHEMA_WEBSOCKET_GET_ENTITIES = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        'type': WS_TYPE_SCHEDULE_ENTITIES
    })

WS_TYPE_SCHEDULE_CLEAR = 'schedule/clear'
SCHEMA_WEBSOCKET_CLEAR = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        'type': WS_TYPE_SCHEDULE_CLEAR
    })

WS_TYPE_SCHEDULE_SAVE = 'schedule/save'
SCHEMA_WEBSOCKET_SAVE = \
    websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
        'type': WS_TYPE_SCHEDULE_SAVE,
        'rules': list
    })

# Valid domains for entities with a schedule
SCHEDULE_VALID_DOMAINS = ['climate', 'switch', 'light', 'input_boolean']
SCHEDULE_SWITCHABLE_DOMAINS = ['switch', 'light', 'input_boolean']


async def async_setup(hass, config):
    """Track states and offer events for switches."""
    monitored_pre = config[DOMAIN].get(CONF_ENTITIES, [])
    monitored = []
    for entity in monitored_pre:
        if check_entity(hass, entity):
            monitored.append(entity)

    hass.data[DOMAIN] = Schedule(hass, monitored)
    await hass.components.frontend.async_register_built_in_panel(
        'schedule', 'Schedule', 'mdi:calendar')

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULE_RULES, hass.data[DOMAIN].websocket_handle_rules,
        SCHEMA_WEBSOCKET_GET_RULES)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULE_ENTITIES, hass.data[DOMAIN].websocket_handle_entities,
        SCHEMA_WEBSOCKET_GET_ENTITIES)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULE_CLEAR, hass.data[DOMAIN].websocket_handle_clear,
        SCHEMA_WEBSOCKET_CLEAR)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SCHEDULE_SAVE, hass.data[DOMAIN].websocket_handle_save,
        SCHEMA_WEBSOCKET_SAVE)

    return True


def check_entity(hass, entity):
    """Check if the entity domain is accepted by the schedule."""
    domain = split_entity_id(entity)[0]
    if domain not in SCHEDULE_VALID_DOMAINS:
        _LOGGER.error("Domain %s is not accepted by the schedule.", domain)
        return False
    return True


class Schedule:
    """Represents a generic schedule."""

    def __init__(self, hass, monitored):
        """Initialize the Schedule."""
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION,
                           STORAGE_KEY)
        self.monitored = monitored
        self.rules = []
        self.unsubs = []
        self.defaults = {}
        self.hass.loop.create_task(self.async_load_rules())

        self.active_status = {}
        async_track_state_change(hass, monitored, self.handle_state)

    def handle_state(self, entity, old_state, new_state):
        """Handle state changes of the monitored entities."""
        # TODO only do this if all entities are loaded
        _LOGGER.info("State change detected for %s", entity)
        self.exec_schedule(dt.now())

    def load_rules_dict(self, loaded_rules):
        """Generate rules array from dictionary."""
        self.rules = []
        for rule in loaded_rules:
            if dt.parse_time(rule['start']) >= dt.parse_time(rule['end']):
                _LOGGER.error("Rule end is before start")
                return None
            self.rules.append(
                Rule(rule))
        self.update_rule_listeners()

    async def async_load_rules(self):
        """Load rules from storage."""
        loaded_rules = await self.store.async_load()
        if loaded_rules is None:
            self.generate_defaults()
            await self.async_save_rules()
        else:
            self.load_rules_dict(loaded_rules["rules"])
            self.defaults = loaded_rules["defaults"]

    def update_rule_listeners(self):
        """Add listeners for all times that have rule changes."""
        for unsub in self.unsubs:
            unsub()

        times_set = set()
        for rule in self.rules:
            times_set.add(rule.start)
            times_set.add(rule.end)
        self.unsubs = []
        for time in times_set:
            r_time = dt.parse_time(time)
            self.unsubs.append(async_track_time_change(self.hass,
                                                       self.exec_schedule,
                                                       hour=r_time.hour,
                                                       minute=r_time.minute,
                                                       second=0))

    async def async_save_rules(self):
        """Save rules to storage."""
        await self.store.async_save({
            'rules': list(map(lambda r: r.to_dict(), self.rules)),
            'defaults': self.defaults
        })

    def generate_defaults(self):
        """Generate default values for the monitored entities."""
        for entity in self.monitored:
            domain = split_entity_id(entity)[0]
            if domain == 'climate':
                self.defaults[entity] = 20
            elif domain in SCHEDULE_SWITCHABLE_DOMAINS:
                self.defaults[entity] = False
            else:
                self.defaults[entity] = False

    def exec_schedule(self, now):
        """Execute the configured schedule."""
        new_state = {}
        # Aggregate active states from all rules
        for rule in self.rules:
            if rule.should_update(now):
                if rule.entity in new_state:
                    _LOGGER.warning(
                        "Overlapping rules running for entity %s!",
                        rule.entity)

                else:
                    new_state[rule.entity] = rule.value

        for entity in self.monitored:
            if entity in new_state:
                value = new_state[entity]
            else:
                value = self.defaults[entity]
            self.setValue(entity, value)
        _LOGGER.info("Schedule executed, result = %s", json.dumps(new_state))
        self.active_status = new_state

    def setValue(self, entity, value):
        """Set the entity value.

        Calls a service based on the entity's domain to set
        the value
        """
        domain = domain = split_entity_id(entity)[0]
        if domain == "climate":
            self.hass.loop.create_task(
                self.hass.services.async_call(
                    'climate',
                    'set_temperature',
                    {
                        'entity_id': entity,
                        'temperature': value
                    }))
        elif domain in SCHEDULE_SWITCHABLE_DOMAINS:
            self.hass.loop.create_task(
                self.hass.services.async_call(
                    domain,
                    'turn_on' if value else 'turn_off',
                    {
                        'entity_id': entity,
                    }))

    @callback
    def websocket_handle_rules(self, hass, connection, msg):
        """Handle getting the rules."""
        connection.send_message(websocket_api.result_message(msg['id'], {
            'rules': list(map(lambda r: r.to_dict(), self.rules))
        }))

    @callback
    def websocket_handle_entities(self, hass, connection, msg):
        """Handle getting the monitored entities."""
        connection.send_message(websocket_api.result_message(msg['id'], {
            'entities': self.monitored
        }))

    @callback
    def websocket_handle_clear(self, hass, connection, msg):
        """Handle clearing all the rules."""
        self.rules = []

        self.hass.loop.create_task(self.async_save_rules())

        connection.send_message(websocket_api.result_message(msg['id'], {
            'completed': True
        }))

    @callback
    def websocket_handle_save(self, hass, connection, msg):
        """Handle updating the rules."""
        self.load_rules_dict(msg["rules"])
        self.hass.loop.create_task(self.async_save_rules())
        connection.send_message(websocket_api.result_message(msg['id'], {
            'completed': True
        }))


class Rule:
    """Represents a rule."""

    def __init__(self, rule_dict):
        """Initialize the rule from a dictionary."""
        self._active = rule_dict['active']
        self._start = rule_dict['start']
        self._end = rule_dict['end']
        self._entity = rule_dict['entity']
        self._value = rule_dict['value']
        self._days = rule_dict['days']

    def to_dict(self):
        """Generate a dictionary containing the rule's information."""
        return {
            'active': self._active,
            'start': self._start,
            'end': self._end,
            'entity': self._entity,
            'value': self._value,
            'days': self._days
        }

    @property
    def active(self):
        """Indicate if the rule is enabled."""
        return self._active

    @property
    def start(self):
        """Start time of the rule."""
        return self._start

    @property
    def end(self):
        """End time of the rule."""
        return self._end

    @property
    def entity(self):
        """Id of the entity affected by the rule."""
        return self._entity

    @property
    def value(self):
        """Value to be set when the rule is active."""
        return self._value

    @property
    def days(self):
        """Days in which rule should run."""
        return self._days

    def should_update(self, time):
        """Calculate if rule is active at the given time."""
        if not self._active:
            return False

        now = dt.as_local(time)
        current_time = now.time()
        start = dt.parse_time(self._start)
        end = dt.parse_time(self._end)
        if (self._days[now.weekday()]
                and start <= current_time
                and current_time < end):
            return True
        return False
