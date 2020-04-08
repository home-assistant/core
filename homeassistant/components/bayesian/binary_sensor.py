"""Use Bayesian Inference to trigger a binary sensor."""
from collections import OrderedDict

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

ATTR_OBSERVATIONS = "observations"
ATTR_OCCURRED_OBSERVATION_ENTITIES = "occurred_observation_entities"
ATTR_PROBABILITY = "probability"
ATTR_PROBABILITY_THRESHOLD = "probability_threshold"

CONF_OBSERVATIONS = "observations"
CONF_PRIOR = "prior"
CONF_TEMPLATE = "template"
CONF_PROBABILITY_THRESHOLD = "probability_threshold"
CONF_P_GIVEN_F = "prob_given_false"
CONF_P_GIVEN_T = "prob_given_true"
CONF_TO_STATE = "to_state"

DEFAULT_NAME = "Bayesian Binary Sensor"
DEFAULT_PROBABILITY_THRESHOLD = 0.5

NUMERIC_STATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: "numeric_state",
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_ABOVE): vol.Coerce(float),
        vol.Optional(CONF_BELOW): vol.Coerce(float),
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

STATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_STATE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TO_STATE): cv.string,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

TEMPLATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_TEMPLATE,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Required(CONF_OBSERVATIONS): vol.Schema(
            vol.All(
                cv.ensure_list,
                [vol.Any(NUMERIC_STATE_SCHEMA, STATE_SCHEMA, TEMPLATE_SCHEMA)],
            )
        ),
        vol.Required(CONF_PRIOR): vol.Coerce(float),
        vol.Optional(
            CONF_PROBABILITY_THRESHOLD, default=DEFAULT_PROBABILITY_THRESHOLD
        ): vol.Coerce(float),
    }
)


def update_probability(prior, prob_given_true, prob_given_false):
    """Update probability using Bayes' rule."""
    numerator = prob_given_true * prior
    denominator = numerator + prob_given_false * (1 - prior)
    probability = numerator / denominator
    return probability


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Bayesian Binary sensor."""
    name = config[CONF_NAME]
    observations = config[CONF_OBSERVATIONS]
    prior = config[CONF_PRIOR]
    probability_threshold = config[CONF_PROBABILITY_THRESHOLD]
    device_class = config.get(CONF_DEVICE_CLASS)

    async_add_entities(
        [
            BayesianBinarySensor(
                name, prior, observations, probability_threshold, device_class
            )
        ],
        True,
    )


class BayesianBinarySensor(BinarySensorDevice):
    """Representation of a Bayesian sensor."""

    def __init__(self, name, prior, observations, probability_threshold, device_class):
        """Initialize the Bayesian sensor."""
        self._name = name
        self._observations = observations
        self._probability_threshold = probability_threshold
        self._device_class = device_class
        self._deviation = False
        self.prior = prior
        self.probability = prior

        self.current_observations = OrderedDict({})

        self.observations_by_entity = self._build_observations_by_entity()

        self.observation_handlers = {
            "numeric_state": self._process_numeric_state,
            "state": self._process_state,
            "template": self._process_template,
        }

    async def async_added_to_hass(self):
        """
        Call when entity about to be added.

        All relevant update logic for instance attributes occurs within this closure.
        Other methods in this class are designed to avoid directly modifying instance
        attributes, by instead focusing on returning relevant data back to this method.

        The goal of this method is to ensure that `self.current_observations` and `self.probability`
        are set on a best-effort basis when this entity is register with hass.

        In addition, this method must register the state listener defined within, which
        will be called any time a relevant entity changes its state.
        """

        @callback
        def async_threshold_sensor_state_listener(entity, _old_state, new_state):
            """
            Handle sensor state changes.

            When a state changes, we must update our list of current observations,
            then calculate the new probability.
            """
            if new_state.state == STATE_UNKNOWN:
                return

            self.current_observations.update(self._record_entity_observations(entity))
            self.probability = self._calculate_new_probability()

            self.hass.async_add_job(self.async_update_ha_state, True)

        self.current_observations.update(self._initialize_current_observations())
        self.probability = self._calculate_new_probability()
        async_track_state_change(
            self.hass,
            self.observations_by_entity,
            async_threshold_sensor_state_listener,
        )

    def _initialize_current_observations(self):
        local_observations = OrderedDict({})
        for entity in self.observations_by_entity:
            local_observations.update(self._record_entity_observations(entity))
        return local_observations

    def _record_entity_observations(self, entity):
        local_observations = OrderedDict({})
        entity_obs_list = self.observations_by_entity[entity]

        for entity_obs in entity_obs_list:
            platform = entity_obs["platform"]

            should_trigger = self.observation_handlers[platform](entity_obs)

            if should_trigger:
                obs_entry = {"entity_id": entity, **entity_obs}
            else:
                obs_entry = None

            local_observations[entity_obs["id"]] = obs_entry

        return local_observations

    def _calculate_new_probability(self):
        prior = self.prior

        for obs in self.current_observations.values():
            if obs is not None:
                prior = update_probability(
                    prior,
                    obs["prob_given_true"],
                    obs.get("prob_given_false", 1 - obs["prob_given_true"]),
                )

        return prior

    def _build_observations_by_entity(self):
        """
        Build and return data structure of the form below.

        {
            "sensor.sensor1": [{"id": 0, ...}, {"id": 1, ...}],
            "sensor.sensor2": [{"id": 2, ...}],
            ...
        }

        Each "observation" must be recognized uniquely, and it should be possible
        for all relevant observations to be looked up via their `entity_id`.
        """

        observations_by_entity = {}
        for ind, obs in enumerate(self._observations):
            obs["id"] = ind

            if "entity_id" in obs:
                entity_ids = [obs["entity_id"]]
            elif "value_template" in obs:
                entity_ids = obs.get(CONF_VALUE_TEMPLATE).extract_entities()

            for e_id in entity_ids:
                obs_list = observations_by_entity.get(e_id, [])
                obs_list.append(obs)
                observations_by_entity[e_id] = obs_list

        return observations_by_entity

    def _process_numeric_state(self, entity_observation):
        """Return True if numeric condition is met."""
        entity = entity_observation["entity_id"]

        should_trigger = condition.async_numeric_state(
            self.hass,
            entity,
            entity_observation.get("below"),
            entity_observation.get("above"),
            None,
            entity_observation,
        )
        return should_trigger

    def _process_state(self, entity_observation):
        """Return True if state conditions are met."""
        entity = entity_observation["entity_id"]

        should_trigger = condition.state(
            self.hass, entity, entity_observation.get("to_state")
        )

        return should_trigger

    def _process_template(self, entity_observation):
        """Return True if template condition is True."""
        template = entity_observation.get(CONF_VALUE_TEMPLATE)
        template.hass = self.hass
        should_trigger = condition.async_template(
            self.hass, template, entity_observation
        )
        return should_trigger

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
        print(self.current_observations)
        print(self.observations_by_entity)
        return {
            ATTR_OBSERVATIONS: list(self.current_observations.values()),
            ATTR_OCCURRED_OBSERVATION_ENTITIES: list(
                {
                    obs.get("entity_id")
                    for obs in self.current_observations.values()
                    if obs is not None
                }
            ),
            ATTR_PROBABILITY: round(self.probability, 2),
            ATTR_PROBABILITY_THRESHOLD: self._probability_threshold,
        }

    async def async_update(self):
        """Get the latest data and update the states."""
        self._deviation = bool(self.probability >= self._probability_threshold)
