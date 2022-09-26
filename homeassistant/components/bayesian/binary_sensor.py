"""Use Bayesian Inference to trigger a binary sensor."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
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
from homeassistant.helpers.template import Template, result_as_boolean
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.yaml.objects import NodeListClass

from . import DOMAIN, PLATFORMS

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
        vol.Required(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

STATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_STATE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TO_STATE): cv.string,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Required(CONF_P_GIVEN_F): vol.Coerce(float),
    },
    required=True,
)

TEMPLATE_SCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_TEMPLATE,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
        vol.Required(CONF_P_GIVEN_F): vol.Coerce(float),
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


def update_probability(
    prior: float, prob_given_true: float, prob_given_false: float
) -> float:
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

    async_add_entities(
        [
            BayesianBinarySensor(
                name, prior, observations, probability_threshold, device_class
            )
        ]
    )


class Ob:
    """Representation of a sensor or template observation."""

    def __init__(
        self,
        # identifier: str,
        entity_id: str | None,
        platform: str,
        prob_given_true: float,
        prob_given_false: float,
        observed: bool | None,
        to_state: str,
        above: float | None,
        below: float | None,
        value_template: Template | None,
    ) -> None:
        """Initialize the Observation."""
        # self.identifier = identifier
        self.entity_id = entity_id
        self.platform = platform
        self.prob_given_true = prob_given_true
        self.prob_given_false = prob_given_false
        self.observed = observed
        self.to_state = to_state
        self.below = below
        self.above = above
        self.value_template = value_template
        self.id: str | None = None

    def to_dict(self) -> dict[str, str | float | bool | None]:
        """Represent Class as a Dict for easier serialization."""

        return {
            "entity_id": self.entity_id,
            "platform": self.platform,
            "prob_given_true": self.prob_given_true,
            "prob_given_false": self.prob_given_false,
            "observed": self.observed,
            "to_state": self.to_state,
            "below": self.below,
            "above": self.above,
            "value_template": str(self.value_template),
            "id": self.id,
        }


class BayesianBinarySensor(BinarySensorEntity):
    """Representation of a Bayesian sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        prior: float,
        observations: list[Any] | NodeListClass,
        probability_threshold: float,
        device_class,
    ) -> None:
        """Initialize the Bayesian sensor."""
        self._attr_name = name
        self._observations = [
            Ob(
                entity_id=x.get("entity_id"),
                platform=x.get("platform"),
                prob_given_false=x.get("prob_given_false"),
                prob_given_true=x.get("prob_given_true"),
                observed=None,
                to_state=x.get("to_state"),
                above=x.get("above"),
                below=x.get("below"),
                value_template=x.get("value_template"),
            )
            for x in observations
        ]
        # self._observations = observations
        _LOGGER.error("TemplateError('%s') ", observations)
        self._probability_threshold = probability_threshold
        self._attr_device_class = device_class
        self._attr_is_on = False
        self._callbacks: list[Any] = []

        self.prior = prior
        self.probability = prior

        self.current_observations: OrderedDict[str, Ob] = OrderedDict({})

        self.observations_by_entity = self._build_observations_by_entity()
        self.observations_by_template = self._build_observations_by_template()

        self.observation_handlers: dict[str, Callable[[Ob], bool | None]] = {
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
                obs.observed = observation
                if entity is not None:
                    obs.entity_id = str(entity)
                if obs.id is None:
                    _LOGGER.error(
                        "An unexpected error obs.id is none for a template entity observation"
                    )
                    obs.id = obs.entity_id
                self.current_observations[obs.id] = obs

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

    @callback
    def _recalculate_and_write_state(self) -> None:
        self.probability = self._calculate_new_probability()
        self._attr_is_on = bool(self.probability >= self._probability_threshold)
        self.async_write_ha_state()

    def _initialize_current_observations(self) -> OrderedDict[str, Ob]:
        local_observations: OrderedDict[str, Ob] = OrderedDict({})
        for entity in self.observations_by_entity:
            local_observations.update(self._record_entity_observations(entity))
        return local_observations

    def _record_entity_observations(self, entity: str) -> OrderedDict[str, Ob]:
        local_observations: OrderedDict[str, Ob] = OrderedDict({})

        for entity_obs in self.observations_by_entity[entity]:
            platform: str = str(entity_obs.platform)

            observation: bool | None = self.observation_handlers[platform](entity_obs)
            entity_obs.observed = observation
            if entity_obs.id is not None:
                local_observations[entity_obs.id] = entity_obs
            else:
                _LOGGER.error(
                    "An entity observation did not have an id, please create an issue on github homeassistant/core: '%s'",
                    entity_obs.to_dict(),
                )

        return local_observations

    def _calculate_new_probability(self) -> float:
        prior = self.prior

        for obs in self.current_observations.values():
            if obs is not None:
                if obs.observed is True:
                    prior = update_probability(
                        prior,
                        obs.prob_given_true,
                        obs.prob_given_false,
                    )
                elif obs.observed is False:
                    prior = update_probability(
                        prior,
                        1 - obs.prob_given_true,
                        1 - obs.prob_given_false,
                    )
                elif obs.observed is None:
                    if obs.entity_id is not None:
                        _LOGGER.debug(
                            "Observation for entity '%s' returned None, it will not be used for Bayesian updating",
                            obs.entity_id,
                        )
                    else:
                        _LOGGER.debug(
                            "Observation for template entity returned None rather than a valid boolean, it will not be used for Bayesian updating",
                        )

        return prior

    def _build_observations_by_entity(self) -> dict[str, list[Ob]]:
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

        observations_by_entity: dict[str, list[Ob]] = {}
        for i, observation in enumerate(self._observations):
            observation.id = str(i)

            if observation.entity_id is None:
                continue
            observations_by_entity.setdefault(observation.entity_id, []).append(
                observation
            )

        for li_of_obs in observations_by_entity.values():
            if len(li_of_obs) == 1:
                continue
            for observation in li_of_obs:
                if observation.platform != "state":
                    continue
                observation.platform = "multi_state"

        return observations_by_entity

    def _build_observations_by_template(self) -> dict[Template, list[Ob]]:
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

        observations_by_template: dict[Template, list[Ob]] = {}
        for ind, observation in enumerate(self._observations):
            if observation.value_template is None:
                continue

            observation.id = str(ind)

            template = observation.value_template
            observations_by_template.setdefault(template, []).append(observation)

        return observations_by_template

    def _process_numeric_state(self, entity_observation: Ob) -> bool | None:
        """Return True if numeric condition is met, return False if not, return None otherwise."""
        entity = entity_observation.entity_id

        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None
            return condition.async_numeric_state(
                self.hass,
                entity,
                entity_observation.below,
                entity_observation.above,
                None,
                entity_observation.to_dict(),
            )
        except ConditionError:
            return None

    def _process_state(self, entity_observation: Ob) -> bool | None:
        """Return True if state conditions are met."""
        entity = entity_observation.entity_id
        assert entity is not None
        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None

            return condition.state(self.hass, entity, entity_observation.to_state)
        except ConditionError:
            return None

    def _process_multi_state(self, entity_observation: Ob) -> bool | None:
        """Return True if state conditions are met, never return false as all other states should have their own probabilities configured."""
        entity = entity_observation.entity_id

        try:
            if condition.state(self.hass, entity, entity_observation.to_state):
                return True
        except ConditionError:
            return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        #
        attr_observations_list: list[dict[str, str | float | bool | None]] = [
            obs.to_dict()
            for obs in self.current_observations.values()
            if obs is not None
        ]

        # for item in attr_observations_list:
        #    item.value_template=None

        return {
            ATTR_OBSERVATIONS: attr_observations_list,
            ATTR_OCCURRED_OBSERVATION_ENTITIES: list(
                {
                    obs.entity_id
                    for obs in self.current_observations.values()
                    if obs is not None
                    and obs.entity_id is not None
                    and obs.observed is not None
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
