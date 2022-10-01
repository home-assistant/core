"""Use Bayesian Inference to trigger a binary sensor."""
from __future__ import annotations

from collections import OrderedDict
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConditionError, TemplateError
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    TrackTemplate,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import result_as_boolean
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS
from .repairs import raise_mirrored_entries, raise_no_prob_given_false

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

_LOGGER = logging.getLogger(__name__)


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
    return numerator / denominator


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bayesian Binary sensor."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config[CONF_NAME]
    observations = config[CONF_OBSERVATIONS]
    prior = config[CONF_PRIOR]
    probability_threshold = config[CONF_PROBABILITY_THRESHOLD]
    device_class = config.get(CONF_DEVICE_CLASS)

    # Should deprecate in some future version (2022.10 at time of writing) & make prob_given_false required in schemas.
    broken_observations: list[dict[str, Any]] = []
    for observation in observations:
        if CONF_P_GIVEN_F not in observation:
            text: str = f"{name}/{observation.get(CONF_ENTITY_ID,'')}{observation.get(CONF_VALUE_TEMPLATE,'')}"
            raise_no_prob_given_false(hass, observation, text)
            _LOGGER.error("Missing prob_given_false YAML entry for %s", text)
            broken_observations.append(observation)
    observations = [x for x in observations if x not in broken_observations]

    async_add_entities(
        [
            BayesianBinarySensor(
                name, prior, observations, probability_threshold, device_class
            )
        ]
    )


class BayesianBinarySensor(BinarySensorEntity):
    """Representation of a Bayesian sensor."""

    _attr_should_poll = False

    def __init__(self, name, prior, observations, probability_threshold, device_class):
        """Initialize the Bayesian sensor."""
        self._attr_name = name
        self._observations = observations
        self._probability_threshold = probability_threshold
        self._attr_device_class = device_class
        self._attr_is_on = False
        self._callbacks = []

        self.prior = prior
        self.probability = prior

        self.current_observations = OrderedDict({})

        self.observations_by_entity = self._build_observations_by_entity()
        self.observations_by_template = self._build_observations_by_template()

        self.observation_handlers = {
            "numeric_state": self._process_numeric_state,
            "state": self._process_state,
            "multi_state": self._process_multi_state,
        }

    async def async_added_to_hass(self) -> None:
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
        def async_threshold_sensor_state_listener(event):
            """
            Handle sensor state changes.

            When a state changes, we must update our list of current observations,
            then calculate the new probability.
            """

            entity = event.data.get("entity_id")

            self.current_observations.update(self._record_entity_observations(entity))
            self.async_set_context(event.context)
            self._recalculate_and_write_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                list(self.observations_by_entity),
                async_threshold_sensor_state_listener,
            )
        )

        @callback
        def _async_template_result_changed(event, updates):
            track_template_result = updates.pop()
            template = track_template_result.template
            result = track_template_result.result
            entity = event and event.data.get("entity_id")
            if isinstance(result, TemplateError):
                _LOGGER.error(
                    "TemplateError('%s') "
                    "while processing template '%s' "
                    "in entity '%s'",
                    result,
                    template,
                    self.entity_id,
                )

                observation = None
            else:
                observation = result_as_boolean(result)

            for obs in self.observations_by_template[template]:
                obs_entry = {"entity_id": entity, "observation": observation, **obs}
                self.current_observations[obs["id"]] = obs_entry

            if event:
                self.async_set_context(event.context)
            self._recalculate_and_write_state()

        for template in self.observations_by_template:
            info = async_track_template_result(
                self.hass,
                [TrackTemplate(template, None)],
                _async_template_result_changed,
            )

            self._callbacks.append(info)
            self.async_on_remove(info.async_remove)
            info.async_refresh()

        self.current_observations.update(self._initialize_current_observations())
        self.probability = self._calculate_new_probability()
        self._attr_is_on = bool(self.probability >= self._probability_threshold)

        # detect mirrored entries
        for entity, observations in self.observations_by_entity.items():
            raise_mirrored_entries(
                self.hass, observations, text=f"{self._attr_name}/{entity}"
            )

        all_template_observations = []
        for value in self.observations_by_template.values():
            all_template_observations.append(value[0])
        if len(all_template_observations) == 2:
            raise_mirrored_entries(
                self.hass,
                all_template_observations,
                text=f"{self._attr_name}/{all_template_observations[0]['value_template']}",
            )

    @callback
    def _recalculate_and_write_state(self):
        self.probability = self._calculate_new_probability()
        self._attr_is_on = bool(self.probability >= self._probability_threshold)
        self.async_write_ha_state()

    def _initialize_current_observations(self):
        local_observations = OrderedDict({})

        for entity in self.observations_by_entity:
            local_observations.update(self._record_entity_observations(entity))
        return local_observations

    def _record_entity_observations(self, entity):
        local_observations = OrderedDict({})

        for entity_obs in self.observations_by_entity[entity]:
            platform = entity_obs["platform"]

            observation = self.observation_handlers[platform](entity_obs)

            obs_entry = {
                "entity_id": entity,
                "observation": observation,
                **entity_obs,
            }
            local_observations[entity_obs["id"]] = obs_entry

        return local_observations

    def _calculate_new_probability(self):
        prior = self.prior

        for obs in self.current_observations.values():
            if obs is not None:
                if obs["observation"] is True:
                    prior = update_probability(
                        prior,
                        obs["prob_given_true"],
                        obs["prob_given_false"],
                    )
                elif obs["observation"] is False:
                    prior = update_probability(
                        prior,
                        1 - obs["prob_given_true"],
                        1 - obs["prob_given_false"],
                    )
                elif obs["observation"] is None:
                    if obs["entity_id"] is not None:
                        _LOGGER.debug(
                            "Observation for entity '%s' returned None, it will not be used for Bayesian updating",
                            obs["entity_id"],
                        )
                    else:
                        _LOGGER.debug(
                            "Observation for template entity returned None rather than a valid boolean, it will not be used for Bayesian updating",
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

        observations_by_entity: dict[str, list[OrderedDict]] = {}
        for i, obs in enumerate(self._observations):
            obs["id"] = i

            if "entity_id" not in obs:
                continue
            observations_by_entity.setdefault(obs["entity_id"], []).append(obs)

        for li_of_dicts in observations_by_entity.values():
            if len(li_of_dicts) == 1:
                continue
            for ord_dict in li_of_dicts:
                if ord_dict["platform"] != "state":
                    continue
                ord_dict["platform"] = "multi_state"

        return observations_by_entity

    def _build_observations_by_template(self):
        """
        Build and return data structure of the form below.

        {
            "template": [{"id": 0, ...}, {"id": 1, ...}],
            "template2": [{"id": 2, ...}],
            ...
        }

        Each "observation" must be recognized uniquely, and it should be possible
        for all relevant observations to be looked up via their `template`.
        """

        observations_by_template = {}
        for ind, obs in enumerate(self._observations):
            obs["id"] = ind

            if "value_template" not in obs:
                continue

            template = obs.get(CONF_VALUE_TEMPLATE)
            observations_by_template.setdefault(template, []).append(obs)

        return observations_by_template

    def _process_numeric_state(self, entity_observation):
        """Return True if numeric condition is met, return False if not, return None otherwise."""
        entity = entity_observation["entity_id"]

        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None
            return condition.async_numeric_state(
                self.hass,
                entity,
                entity_observation.get("below"),
                entity_observation.get("above"),
                None,
                entity_observation,
            )
        except ConditionError:
            return None

    def _process_state(self, entity_observation):
        """Return True if state conditions are met."""
        entity = entity_observation["entity_id"]

        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None

            return condition.state(
                self.hass, entity, entity_observation.get("to_state")
            )
        except ConditionError:
            return None

    def _process_multi_state(self, entity_observation):
        """Return True if state conditions are met."""
        entity = entity_observation["entity_id"]

        try:
            if condition.state(self.hass, entity, entity_observation.get("to_state")):
                return True
        except ConditionError:
            return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr_observations_list = [
            obs.copy() for obs in self.current_observations.values() if obs is not None
        ]

        for item in attr_observations_list:
            item.pop("value_template", None)

        return {
            ATTR_OBSERVATIONS: attr_observations_list,
            ATTR_OCCURRED_OBSERVATION_ENTITIES: list(
                {
                    obs.get("entity_id")
                    for obs in self.current_observations.values()
                    if obs is not None
                    and obs.get("entity_id") is not None
                    and obs.get("observation") is not None
                }
            ),
            ATTR_PROBABILITY: round(self.probability, 2),
            ATTR_PROBABILITY_THRESHOLD: self._probability_threshold,
        }

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        if not self._callbacks:
            self._recalculate_and_write_state()
            return
        # Force recalc of the templates. The states will
        # update automatically.
        for call in self._callbacks:
            call.async_refresh()
