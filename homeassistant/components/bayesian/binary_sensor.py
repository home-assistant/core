"""
Use Bayesian Inference to trigger a binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.bayesian/
"""
from collections import OrderedDict

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA, BinarySensorDevice)
from homeassistant.const import (
    CONF_ABOVE, CONF_BELOW, CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_NAME,
    CONF_PLATFORM, CONF_STATE, CONF_VALUE_TEMPLATE, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

ATTR_OBSERVATIONS = 'observations'
ATTR_PROBABILITY = 'probability'
ATTR_PROBABILITY_THRESHOLD = 'probability_threshold'

CONF_OBSERVATIONS = 'observations'
CONF_PRIOR = 'prior'
CONF_TEMPLATE = "template"
CONF_PROBABILITY_THRESHOLD = 'probability_threshold'
CONF_P_GIVEN_F = 'prob_given_false'
CONF_P_GIVEN_T = 'prob_given_true'
CONF_TO_STATE = 'to_state'

DEFAULT_NAME = "Bayesian Binary Sensor"
DEFAULT_PROBABILITY_THRESHOLD = 0.5

NUMERIC_STATE_SCHEMA = vol.Schema({
    CONF_PLATFORM: 'numeric_state',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ABOVE): vol.Coerce(float),
    vol.Optional(CONF_BELOW): vol.Coerce(float),
    vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
    vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float)
}, required=True)

STATE_SCHEMA = vol.Schema({
    CONF_PLATFORM: CONF_STATE,
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_TO_STATE): cv.string,
    vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
    vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float)
}, required=True)

TEMPLATE_SCHEMA = vol.Schema({
    CONF_PLATFORM: CONF_TEMPLATE,
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
    vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float)
}, required=True)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): cv.string,
    vol.Required(CONF_OBSERVATIONS):
        vol.Schema(vol.All(cv.ensure_list,
                           [vol.Any(NUMERIC_STATE_SCHEMA, STATE_SCHEMA,
                                    TEMPLATE_SCHEMA)])),
    vol.Required(CONF_PRIOR): vol.Coerce(float),
    vol.Optional(CONF_PROBABILITY_THRESHOLD,
                 default=DEFAULT_PROBABILITY_THRESHOLD): vol.Coerce(float),
})


def update_probability(prior, prob_true, prob_false):
    """Update probability using Bayes' rule."""
    numerator = prob_true * prior
    denominator = numerator + prob_false * (1 - prior)
    probability = numerator / denominator
    return probability


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Bayesian Binary sensor."""
    name = config.get(CONF_NAME)
    observations = config.get(CONF_OBSERVATIONS)
    prior = config.get(CONF_PRIOR)
    probability_threshold = config.get(CONF_PROBABILITY_THRESHOLD)
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_entities([
        BayesianBinarySensor(
            name, prior, observations, probability_threshold, device_class)
    ], True)


class BayesianBinarySensor(BinarySensorDevice):
    """Representation of a Bayesian sensor."""

    def __init__(self, name, prior, observations, probability_threshold,
                 device_class):
        """Initialize the Bayesian sensor."""
        self._name = name
        self._observations = observations
        self._probability_threshold = probability_threshold
        self._device_class = device_class
        self._deviation = False
        self.prior = prior
        self.probability = prior

        self.current_obs = OrderedDict({})

        to_observe = set()
        for obs in self._observations:
            if 'entity_id' in obs:
                to_observe.update(set([obs.get('entity_id')]))
            if 'value_template' in obs:
                to_observe.update(
                    set(obs.get(CONF_VALUE_TEMPLATE).extract_entities()))
        self.entity_obs = dict.fromkeys(to_observe, [])

        for ind, obs in enumerate(self._observations):
            obs['id'] = ind
            if 'entity_id' in obs:
                self.entity_obs[obs['entity_id']].append(obs)
            if 'value_template' in obs:
                for ent in obs.get(CONF_VALUE_TEMPLATE).extract_entities():
                    self.entity_obs[ent].append(obs)

        self.watchers = {
            'numeric_state': self._process_numeric_state,
            'state': self._process_state,
            'template': self._process_template
        }

    async def async_added_to_hass(self):
        """Call when entity about to be added."""
        @callback
        def async_threshold_sensor_state_listener(entity, old_state,
                                                  new_state):
            """Handle sensor state changes."""
            if new_state.state == STATE_UNKNOWN:
                return

            entity_obs_list = self.entity_obs[entity]

            for entity_obs in entity_obs_list:
                platform = entity_obs['platform']

                self.watchers[platform](entity_obs)

            prior = self.prior
            for obs in self.current_obs.values():
                prior = update_probability(
                    prior, obs['prob_true'], obs['prob_false'])
            self.probability = prior

            self.hass.async_add_job(self.async_update_ha_state, True)

        async_track_state_change(
            self.hass, self.entity_obs, async_threshold_sensor_state_listener)

    def _update_current_obs(self, entity_observation, should_trigger):
        """Update current observation."""
        obs_id = entity_observation['id']

        if should_trigger:
            prob_true = entity_observation['prob_given_true']
            prob_false = entity_observation.get(
                'prob_given_false', 1 - prob_true)

            self.current_obs[obs_id] = {
                'prob_true': prob_true,
                'prob_false': prob_false
            }

        else:
            self.current_obs.pop(obs_id, None)

    def _process_numeric_state(self, entity_observation):
        """Add entity to current_obs if numeric state conditions are met."""
        entity = entity_observation['entity_id']

        should_trigger = condition.async_numeric_state(
            self.hass, entity,
            entity_observation.get('below'),
            entity_observation.get('above'), None, entity_observation)

        self._update_current_obs(entity_observation, should_trigger)

    def _process_state(self, entity_observation):
        """Add entity to current observations if state conditions are met."""
        entity = entity_observation['entity_id']

        should_trigger = condition.state(
            self.hass, entity, entity_observation.get('to_state'))

        self._update_current_obs(entity_observation, should_trigger)

    def _process_template(self, entity_observation):
        """Add entity to current_obs if template is true."""
        template = entity_observation.get(CONF_VALUE_TEMPLATE)
        template.hass = self.hass
        should_trigger = condition.async_template(
            self.hass, template, entity_observation)
        self._update_current_obs(entity_observation, should_trigger)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._deviation

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_OBSERVATIONS: [val for val in self.current_obs.values()],
            ATTR_PROBABILITY: round(self.probability, 2),
            ATTR_PROBABILITY_THRESHOLD: self._probability_threshold,
        }

    async def async_update(self):
        """Get the latest data and update the states."""
        self._deviation = bool(self.probability >= self._probability_threshold)
