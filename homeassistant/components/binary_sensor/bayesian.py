"""
Use Bayesian Inference to trigger a binary sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bayesian_binary/
"""
import asyncio
import logging
from collections import OrderedDict

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (BinarySensorDevice,
                                                    PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, STATE_UNKNOWN, CONF_DEVICE_CLASS)
from homeassistant.core import callback
from homeassistant.helpers import condition
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

CONF_PROBABILITY_THRESHOLD = 'probability_threshold'
CONF_OBSERVATIONS = 'observations'
CONF_PRIOR = 'prior'

DEFAULT_NAME = 'BayesianBinary'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME):
    cv.string,
    vol.Required(CONF_OBSERVATIONS):
    vol.Schema([dict]),
    vol.Required(CONF_PRIOR):
    vol.Coerce(float),
    vol.Required(CONF_PROBABILITY_THRESHOLD):
    vol.Coerce(float),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Threshold sensor."""
    name = config.get(CONF_NAME)
    observations = config.get(CONF_OBSERVATIONS)
    prior = config.get(CONF_PRIOR)
    probability_threshold = config.get(CONF_PROBABILITY_THRESHOLD)
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_devices([
        BayesianBinarySensor(hass, name, prior, observations,
                             probability_threshold, device_class)
    ], True)
    return True


class BayesianBinarySensor(BinarySensorDevice):
    """Representation of a Bayesian sensor."""

    def __init__(self, hass, name, prior, observations, probability_threshold,
                 device_class):
        """Initialize the Bayesian sensor."""
        self._hass = hass
        self._name = name
        self._observations = observations
        self._probability_threshold = probability_threshold
        self._device_class = device_class
        self._deviation = False
        self.prior = prior
        self.probability = prior

        self.current_obs = OrderedDict({})

        self.entity_obs = {obs['entity_id']: obs for obs in self._observations}

        self.watchers = {
            'numeric_state': self._process_numeric_state,
            'state': self._process_state
        }

        @callback
        # pylint: disable=invalid-name
        def async_threshold_sensor_state_listener(entity, old_state,
                                                  new_state):
            """Handle sensor state changes."""
            if new_state.state == STATE_UNKNOWN:
                return

            entity_obs = self.entity_obs[entity]
            platform = entity_obs['platform']

            self.watchers[platform](entity_obs)

            prior = self.prior
            for obs in self.current_obs.values():
                prior = self._update_probability(obs, prior)

            self.probability = prior

            hass.async_add_job(self.async_update_ha_state, True)

        for obs in self._observations:
            entity_id = obs['entity_id']
            async_track_state_change(hass, entity_id,
                                     async_threshold_sensor_state_listener)

    def _process_numeric_state(self, entity_observation):
        entity = entity_observation['entity_id']
        if condition.async_numeric_state(self._hass, entity,
                                         entity_observation.get('below'),
                                         entity_observation.get('above'), None,
                                         entity_observation):

            self.current_obs[entity] = entity_observation['probability']

        else:
            self.current_obs.pop(entity, None)

    def _process_state(self, entity_observation):
        entity = entity_observation['entity_id']
        if condition.state(self._hass, entity,
                           entity_observation.get('to_state')):

            self.current_obs[entity] = entity_observation['probability']

        else:
            self.current_obs.pop(entity, None)

    @staticmethod
    def _update_probability(prior, observation):
        prob_pos = observation
        prob_neg = 1 - prob_pos

        numerator = prob_pos * prior
        denominator = numerator + prob_neg * (1 - prior)

        probability = numerator / denominator

        return probability

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
            'observations': [val for val in self.current_obs.values()],
            'probability': self.probability,
            'probability_threshold': self._probability_threshold
        }

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        self._deviation = bool(self.probability > self._probability_threshold)
