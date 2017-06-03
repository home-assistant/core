"""
Support for switches that transition states/attributes of other components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.transition/
"""
import asyncio
import logging
import math
import re

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT, SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, CONF_SWITCHES)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

CONF_HOURS = 'hours'
CONF_MINUTES = 'minutes'
CONF_SECONDS = 'seconds'

ATTR_DURATION = 'duration'
ATTR_EASING = 'easing'
ATTR_POSITION = 'position'
ATTR_SERVICE = 'service'
ATTR_STEPS = 'steps'
ATTR_TO = 'to'

DEFAULT_EASING = 'linear'
DEFAULT_POSITION = 0
DEFAULT_STEPS = 60
DEFAULT_DURATION = {CONF_MINUTES: 1}

EASINGS = {}
EASINGS['linear'] = lambda t: t
EASINGS['easeInQuad'] = lambda t: math.pow(t, 2)
EASINGS['easeInCubic'] = lambda t: math.pow(t, 3)
EASINGS['easeInQuart'] = lambda t: math.pow(t, 4)
EASINGS['easeInQuint'] = lambda t: math.pow(t, 5)
EASINGS['easeInExpo'] = lambda t: 0 if t == 0 else math.pow(2, 10*(t-1))
EASINGS['easeInSin'] = lambda t: 1+math.sin(math.pi/2*t-math.pi/2)
EASINGS['easeInElastic'] = lambda t: math.sin(t*6.5*math.pi)*t*t
EASINGS['easeInBack'] = lambda t: t*t*(2.70158*t-1.70158)

SWITCH_SCHEMA = vol.Schema({
    vol.Required(ATTR_DURATION, default=DEFAULT_DURATION):
        cv.time_period_dict,
    vol.Required(ATTR_ENTITY_ID):
        cv.entity_ids,
    vol.Required(ATTR_SERVICE):
        cv.service,
    vol.Required(ATTR_TO):
        vol.Any(int, float, dict),
    vol.Optional(ATTR_EASING, default=DEFAULT_EASING):
        cv.string,
    vol.Optional(ATTR_STEPS, default=DEFAULT_STEPS):
        cv.positive_int,
    vol.Optional(ATTR_POSITION, default=DEFAULT_POSITION):
        cv.positive_int,
    vol.Optional(ATTR_FRIENDLY_NAME):
        cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the transition switches."""
    switches = []

    # Create easeOut and easeInOut function from the easeIn functions:
    keys = list(EASINGS.keys())
    pattern = re.compile('easeIn(?!Out)')
    easingkeys = filter(pattern.search, keys)

    for easingkey in easingkeys:
        # flake8: disable=E211
        # pylint: disable=undefined-variable
        if not re.sub('easeIn', 'easeOut', easingkey) in EASINGS:
            EASINGS[re.sub('easeIn', 'easeOut', easingkey)] = (
                lambda easing: lambda t: 1-EASINGS[re.sub(
                    'easeOut', 'easeIn', easing)](1-t))(easingkey)
        if not re.sub('easeIn', 'easeInOut', easingkey) in EASINGS:
            EASINGS[re.sub('easeIn', 'easeInOut', easingkey)] = (
                lambda easing: lambda t: EASINGS[easing](
                    t*2)/2 if t < 0.5 else EASINGS[re.sub(
                        'easeIn', 'easeOut', easing)](
                            (t-0.5)*2)/2+0.5)(easingkey)

    for device, device_config in config[CONF_SWITCHES].items():
        duration = device_config.get(ATTR_DURATION)
        easing = device_config.get(ATTR_EASING)
        entity_ids = device_config.get(ATTR_ENTITY_ID)
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        position = device_config.get(ATTR_POSITION)
        service = device_config.get(ATTR_SERVICE)
        steps = device_config.get(ATTR_STEPS)
        to_values = device_config.get(ATTR_TO)

        switches.append(
            TransitionSwitch(
                hass,
                device,
                friendly_name,
                entity_ids,
                service,
                to_values,
                duration,
                steps,
                position,
                easing)
            )
    if not switches:
        _LOGGER.error("No switches added")
        return False

    yield from async_add_devices(switches, True)
    return True


class TransitionSwitch(SwitchDevice):
    """Representation of a transition switch."""

    def __init__(self, hass, device_id, friendly_name, entity_ids, service,
                 toValue, duration, steps, position, easing):
        """Initialize the transition switch."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id,
                                                  hass=hass)
        self._name = friendly_name
        self._state = False
        self.entity_ids = entity_ids
        self.service = service
        self.from_values = {}
        self.to_value = toValue
        self.duration = duration
        self.steps = steps
        self.position = position
        self.easing = easing
        self.stop_transition_interval = None
        self.current_step = 0
        self.all_the_same = True

        if not isinstance(self.entity_ids, list):
            self.entity_ids = [self.entity_ids]

    def determine_from_values(self, keys_from, values_from):
        """Determine the starting values to apply the transition to."""
        if isinstance(keys_from, dict):
            attributes_to = {}
            for val_name in keys_from:
                attributes_to[val_name] = self.determine_from_values(
                    keys_from[val_name], values_from[val_name])
        else:
            attributes_to = values_from
        return attributes_to

    def determine_intermediate_values(self, from_values, to_values, position):
        """Determine the current values for the attributes."""
        if isinstance(to_values, dict):
            attributes_to = {}
            for val_name in to_values:
                attributes_to[val_name] = self.determine_intermediate_values(
                    from_values[val_name], to_values[val_name], position)
        else:
            attributes_to = float(from_values) + (
                (float(to_values) - float(from_values)) * position)
        return attributes_to

    @asyncio.coroutine
    def async_update_transition(self, now):
        """Set attributes of entities."""
        service_domain, service_action = self.service.split('.')
        position = EASINGS[self.easing](self.current_step / self.steps)

        if self.all_the_same:
            to_values = self.determine_intermediate_values(
                self.from_values[self.entity_ids[0]], self.to_value, position)
            service_data = {'entity_id': self.entity_ids}
            if isinstance(to_values, dict):
                service_data.update(to_values)
            else:
                service_data['value'] = to_values
            self.hass.async_add_job(
                self.hass.services.async_call(
                    service_domain, service_action, service_data))
        else:
            for entity_id in self.entity_ids:
                to_values = self.determine_intermediate_values(
                    self.from_values[entity_id], self.to_value, position)
                service_data = {'entity_id': entity_id}
                if isinstance(to_values, dict):
                    service_data.update(to_values)
                else:
                    service_data['value'] = to_values
                self.hass.async_add_job(
                    self.hass.services.async_call(
                        service_domain, service_action, service_data))

        if self.current_step >= self.steps:
            self.stop_transition_interval()
            self.stop_transition_interval = None
            self._state = False
            self.schedule_update_ha_state()
        self.current_step = self.current_step + 1

    def start_transition(self):
        """Start the transition."""
        for entity_id in self.entity_ids:
            state = self.hass.states.get(entity_id)
            if isinstance(self.to_value, dict):
                self.from_values[entity_id] = self.determine_from_values(
                    self.to_value, state.attributes)
            else:
                self.from_values[entity_id] = self.determine_from_values(
                    self.to_value, state.state)

        self.all_the_same = True
        first_id = self.entity_ids[0]
        for entity_id in self.from_values:
            if self.from_values[entity_id] != self.from_values[first_id]:
                self.all_the_same = False
                break

        interval = self.duration / self.steps
        self.stop_transition_interval = async_track_time_interval(
            self.hass, self.async_update_transition, interval)
        self.hass.async_add_job(self.async_update_transition, None)
        self.current_step = self.position

    @property
    def should_poll(self):
        """No polling needed for this switch."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if not self._state:
            self.start_transition()
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._state:
            self.stop_transition_interval()
            self.stop_transition_interval = None
            self._state = False
            self.schedule_update_ha_state()
