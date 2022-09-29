"""Helpers to deal with bayesian observations."""
from __future__ import annotations

import uuid

from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers.template import Template

from .const import CONF_P_GIVEN_F, CONF_P_GIVEN_T, CONF_TO_STATE


class Observation:
    """Representation of a sensor or template observation."""

    def __init__(
        self,
        entity_id: str | None,
        platform: str,
        prob_given_true: float,
        prob_given_false: float,
        observed: bool | None,
        to_state: str | None,
        above: float | None,
        below: float | None,
        value_template: Template | None,
    ) -> None:
        """Initialize the Observation."""
        self.entity_id = entity_id
        self.platform = platform
        self.prob_given_true = prob_given_true
        self.prob_given_false = prob_given_false
        self.observed = observed
        self.to_state = to_state
        self.below = below
        self.above = above
        self.value_template = value_template
        self.id: str = str(uuid.uuid4())

    def to_dict(self) -> dict[str, str | float | bool | None]:
        """Represent Class as a Dict for easier serialization."""

        dic = {
            CONF_PLATFORM: self.platform,
            CONF_ENTITY_ID: self.entity_id,
            CONF_VALUE_TEMPLATE: self.template,
            CONF_TO_STATE: self.to_state,
            CONF_ABOVE: self.above,
            CONF_BELOW: self.below,
            CONF_P_GIVEN_T: self.prob_given_true,
            CONF_P_GIVEN_F: self.prob_given_false,
            "observed": self.observed,
        }

        for key, value in dic.copy().items():
            if value is None:
                del dic[key]

        return dic

    @property
    def template(self) -> str | None:
        """Not all observations have templates and we want to get template strings."""
        if self.value_template is not None:
            return self.value_template.template
        return None
