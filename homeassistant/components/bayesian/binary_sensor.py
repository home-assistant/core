"""Use Bayesian Inference to trigger a binary sensor."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
import logging
import math
from typing import TYPE_CHECKING, Any, NamedTuple
from uuid import UUID

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ConditionError, TemplateError
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import Template, result_as_boolean
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS
from .const import (
    ATTR_OBSERVATIONS,
    ATTR_OCCURRED_OBSERVATION_ENTITIES,
    ATTR_PROBABILITY,
    ATTR_PROBABILITY_THRESHOLD,
    CONF_NUMERIC_STATE,
    CONF_OBSERVATIONS,
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    CONF_TEMPLATE,
    CONF_TO_STATE,
    DEFAULT_NAME,
    DEFAULT_PROBABILITY_THRESHOLD,
)
from .helpers import Observation
from .issues import raise_mirrored_entries, raise_no_prob_given_false

_LOGGER = logging.getLogger(__name__)


def _above_greater_than_below(config: dict[str, Any]) -> dict[str, Any]:
    if config[CONF_PLATFORM] == CONF_NUMERIC_STATE:
        above = config.get(CONF_ABOVE)
        below = config.get(CONF_BELOW)
        if above is None and below is None:
            _LOGGER.error(
                "For bayesian numeric state for entity: %s at least one of 'above' or 'below' must be specified",
                config[CONF_ENTITY_ID],
            )
            raise vol.Invalid(
                "For bayesian numeric state at least one of 'above' or 'below' must be specified."
            )
        if above is not None and below is not None:
            if above > below:
                _LOGGER.error(
                    "For bayesian numeric state 'above' (%s) must be less than 'below' (%s)",
                    above,
                    below,
                )
                raise vol.Invalid("'above' is greater than 'below'")
    return config


NUMERIC_STATE_SCHEMA = vol.All(
    vol.Schema(
        {
            CONF_PLATFORM: CONF_NUMERIC_STATE,
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_ABOVE): vol.Coerce(float),
            vol.Optional(CONF_BELOW): vol.Coerce(float),
            vol.Required(CONF_P_GIVEN_T): vol.Coerce(float),
            vol.Optional(CONF_P_GIVEN_F): vol.Coerce(float),
        },
        required=True,
    ),
    _above_greater_than_below,
)


def _no_overlapping(configs: list[dict]) -> list[dict]:
    numeric_configs = [
        config for config in configs if config[CONF_PLATFORM] == CONF_NUMERIC_STATE
    ]
    if len(numeric_configs) < 2:
        return configs

    class NumericConfig(NamedTuple):
        above: float
        below: float

    d: dict[str, list[NumericConfig]] = {}
    for _, config in enumerate(numeric_configs):
        above = config.get(CONF_ABOVE, -math.inf)
        below = config.get(CONF_BELOW, math.inf)
        entity_id: str = str(config[CONF_ENTITY_ID])
        d.setdefault(entity_id, []).append(NumericConfig(above, below))

    for ent_id, intervals in d.items():
        intervals = sorted(intervals, key=lambda tup: tup.above)

        for i, tup in enumerate(intervals):
            if len(intervals) > i + 1 and tup.below > intervals[i + 1].above:
                raise vol.Invalid(
                    "Ranges for bayesian numeric state entities must not overlap, "
                    f"but {ent_id} has overlapping ranges, above:{tup.above}, "
                    f"below:{tup.below} overlaps with above:{intervals[i + 1].above}, "
                    f"below:{intervals[i + 1].below}."
                )
    return configs


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

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): cv.string,
        vol.Required(CONF_OBSERVATIONS): vol.Schema(
            vol.All(
                cv.ensure_list,
                [vol.Any(TEMPLATE_SCHEMA, STATE_SCHEMA, NUMERIC_STATE_SCHEMA)],
                _no_overlapping,
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

    name: str = config[CONF_NAME]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)
    observations: list[ConfigType] = config[CONF_OBSERVATIONS]
    prior: float = config[CONF_PRIOR]
    probability_threshold: float = config[CONF_PROBABILITY_THRESHOLD]
    device_class: BinarySensorDeviceClass | None = config.get(CONF_DEVICE_CLASS)

    # Should deprecate in some future version (2022.10 at time of writing) & make prob_given_false required in schemas.
    broken_observations: list[dict[str, Any]] = []
    for observation in observations:
        if CONF_P_GIVEN_F not in observation:
            text = (
                f"{name}/{observation.get(CONF_ENTITY_ID, '')}"
                f"{observation.get(CONF_VALUE_TEMPLATE, '')}"
            )
            raise_no_prob_given_false(hass, text)
            _LOGGER.error("Missing prob_given_false YAML entry for %s", text)
            broken_observations.append(observation)
    observations = [x for x in observations if x not in broken_observations]

    async_add_entities(
        [
            BayesianBinarySensor(
                name,
                unique_id,
                prior,
                observations,
                probability_threshold,
                device_class,
            )
        ]
    )


class BayesianBinarySensor(BinarySensorEntity):
    """Representation of a Bayesian sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        unique_id: str | None,
        prior: float,
        observations: list[ConfigType],
        probability_threshold: float,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize the Bayesian sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id and f"bayesian-{unique_id}"
        self._observations = [
            Observation(
                entity_id=observation.get(CONF_ENTITY_ID),
                platform=observation[CONF_PLATFORM],
                prob_given_false=observation[CONF_P_GIVEN_F],
                prob_given_true=observation[CONF_P_GIVEN_T],
                observed=None,
                to_state=observation.get(CONF_TO_STATE),
                above=observation.get(CONF_ABOVE),
                below=observation.get(CONF_BELOW),
                value_template=observation.get(CONF_VALUE_TEMPLATE),
            )
            for observation in observations
        ]
        self._probability_threshold = probability_threshold
        self._attr_device_class = device_class
        self._attr_is_on = False
        self._callbacks: list[TrackTemplateResultInfo] = []

        self.prior = prior
        self.probability = prior

        self.current_observations: OrderedDict[UUID, Observation] = OrderedDict({})

        self.observations_by_entity = self._build_observations_by_entity()
        self.observations_by_template = self._build_observations_by_template()

        self.observation_handlers: dict[
            str, Callable[[Observation, bool], bool | None]
        ] = {
            "numeric_state": self._process_numeric_state,
            "state": self._process_state,
        }

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added.

        All relevant update logic for instance attributes occurs within this closure.
        Other methods in this class are designed to avoid directly modifying instance
        attributes, by instead focusing on returning relevant data back to this method.

        The goal of this method is to ensure that `self.current_observations` and `self.probability`
        are set on a best-effort basis when this entity is register with hass.

        In addition, this method must register the state listener defined within, which
        will be called any time a relevant entity changes its state.
        """

        @callback
        def async_threshold_sensor_state_listener(
            event: Event[EventStateChangedData],
        ) -> None:
            """Handle sensor state changes.

            When a state changes, we must update our list of current observations,
            then calculate the new probability.
            """

            entity_id = event.data["entity_id"]

            self.current_observations.update(
                self._record_entity_observations(entity_id)
            )
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
        def _async_template_result_changed(
            event: Event[EventStateChangedData] | None,
            updates: list[TrackTemplateResult],
        ) -> None:
            track_template_result = updates.pop()
            template = track_template_result.template
            result = track_template_result.result
            entity_id = None if event is None else event.data["entity_id"]
            if isinstance(result, TemplateError):
                _LOGGER.error(
                    "TemplateError('%s') while processing template '%s' in entity '%s'",
                    result,
                    template,
                    self.entity_id,
                )

                observed = None
            else:
                observed = result_as_boolean(result)

            for observation in self.observations_by_template[template]:
                observation.observed = observed

                # in some cases a template may update because of the absence of an entity
                if entity_id is not None:
                    observation.entity_id = entity_id

                self.current_observations[observation.id] = observation

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
        self._attr_is_on = self.probability >= self._probability_threshold

        # detect mirrored entries
        for entity, observations in self.observations_by_entity.items():
            raise_mirrored_entries(
                self.hass, observations, text=f"{self._attr_name}/{entity}"
            )

        all_template_observations: list[Observation] = [
            observations[0] for observations in self.observations_by_template.values()
        ]
        if len(all_template_observations) == 2:
            raise_mirrored_entries(
                self.hass,
                all_template_observations,
                text=f"{self._attr_name}/{all_template_observations[0].value_template}",
            )

    @callback
    def _recalculate_and_write_state(self) -> None:
        self.probability = self._calculate_new_probability()
        self._attr_is_on = bool(self.probability >= self._probability_threshold)
        self.async_write_ha_state()

    def _initialize_current_observations(self) -> OrderedDict[UUID, Observation]:
        local_observations: OrderedDict[UUID, Observation] = OrderedDict({})
        for entity in self.observations_by_entity:
            local_observations.update(self._record_entity_observations(entity))
        return local_observations

    def _record_entity_observations(
        self, entity: str
    ) -> OrderedDict[UUID, Observation]:
        local_observations: OrderedDict[UUID, Observation] = OrderedDict({})

        for observation in self.observations_by_entity[entity]:
            platform = observation.platform

            observation.observed = self.observation_handlers[platform](
                observation, observation.multi
            )
            local_observations[observation.id] = observation

        return local_observations

    def _calculate_new_probability(self) -> float:
        prior = self.prior

        for observation in self.current_observations.values():
            if observation.observed is True:
                prior = update_probability(
                    prior,
                    observation.prob_given_true,
                    observation.prob_given_false,
                )
                continue
            if observation.observed is False:
                prior = update_probability(
                    prior,
                    1 - observation.prob_given_true,
                    1 - observation.prob_given_false,
                )
                continue
            # observation.observed is None
            if observation.entity_id is not None:
                _LOGGER.debug(
                    (
                        "Observation for entity '%s' returned None, it will not be used"
                        " for Bayesian updating"
                    ),
                    observation.entity_id,
                )
                continue
            _LOGGER.debug(
                (
                    "Observation for template entity returned None rather than a valid"
                    " boolean, it will not be used for Bayesian updating"
                ),
            )
        # the prior has been updated and is now the posterior
        return prior

    def _build_observations_by_entity(self) -> dict[str, list[Observation]]:
        """Build and return data structure of the form below.

        {
            "sensor.sensor1": [Observation, Observation],
            "sensor.sensor2": [Observation],
            ...
        }

        Each "observation" must be recognized uniquely, and it should be possible
        for all relevant observations to be looked up via their `entity_id`.
        """

        observations_by_entity: dict[str, list[Observation]] = {}
        for observation in self._observations:
            if (key := observation.entity_id) is None:
                continue
            observations_by_entity.setdefault(key, []).append(observation)

        for entity_observations in observations_by_entity.values():
            if len(entity_observations) == 1:
                continue
            for observation in entity_observations:
                observation.multi = True

        return observations_by_entity

    def _build_observations_by_template(self) -> dict[Template, list[Observation]]:
        """Build and return data structure of the form below.

        {
            "template": [Observation, Observation],
            "template2": [Observation],
            ...
        }

        Each "observation" must be recognized uniquely, and it should be possible
        for all relevant observations to be looked up via their `template`.
        """

        observations_by_template: dict[Template, list[Observation]] = {}
        for observation in self._observations:
            if observation.value_template is None:
                continue

            template = observation.value_template
            observations_by_template.setdefault(template, []).append(observation)

        return observations_by_template

    def _process_numeric_state(
        self, entity_observation: Observation, multi: bool = False
    ) -> bool | None:
        """Return True if numeric condition is met, return False if not, return None otherwise."""
        entity_id = entity_observation.entity_id
        # if we are dealing with numeric_state observations entity_id cannot be None
        if TYPE_CHECKING:
            assert entity_id is not None

        entity = self.hass.states.get(entity_id)
        if entity is None:
            return None

        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None
            result = condition.async_numeric_state(
                self.hass,
                entity,
                entity_observation.below,
                entity_observation.above,
                None,
                entity_observation.to_dict(),
            )
            if result:
                return True
            if multi:
                state = float(entity.state)
                if (
                    entity_observation.below is not None
                    and state == entity_observation.below
                ):
                    return True
                return None
        except ConditionError:
            return None
        else:
            return False

    def _process_state(
        self, entity_observation: Observation, multi: bool = False
    ) -> bool | None:
        """Return True if state conditions are met, return False if they are not.

        Returns None if the state is unavailable.
        """

        entity = entity_observation.entity_id

        try:
            if condition.state(self.hass, entity, [STATE_UNKNOWN, STATE_UNAVAILABLE]):
                return None

            result = condition.state(self.hass, entity, entity_observation.to_state)
            if multi and not result:
                return None
        except ConditionError:
            return None
        else:
            return result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""

        return {
            ATTR_PROBABILITY: round(self.probability, 2),
            ATTR_PROBABILITY_THRESHOLD: self._probability_threshold,
            # An entity can be in more than one observation so set then list to deduplicate
            ATTR_OCCURRED_OBSERVATION_ENTITIES: list(
                {
                    observation.entity_id
                    for observation in self.current_observations.values()
                    if observation is not None
                    and observation.entity_id is not None
                    and observation.observed is not None
                }
            ),
            ATTR_OBSERVATIONS: [
                observation.to_dict()
                for observation in self.current_observations.values()
                if observation is not None
            ],
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
