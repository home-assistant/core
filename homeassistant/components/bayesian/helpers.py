"""Helpers to deal with bayesian observations."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class Observation:
    """Representation of a sensor or template observation.

    Either entity_id or value_template should be non-None.
    """

    entity_id: str | None
    platform: str
    prob_given_true: float
    prob_given_false: float
    to_state: str | None
    above: float | None
    below: float | None
    value_template: Template | None
    observed: bool | None = None
    multi: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def to_dict(self) -> dict[str, str | float | bool | None]:
        """Represent Class as a Dict for easier serialization."""

        # Needed because dataclasses asdict() can't serialize Templates and ignores Properties.
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

    def is_mirror(self, other: Observation) -> bool:
        """Dectects whether given observation is a mirror of this one."""
        return (
            self.platform == other.platform
            and round(self.prob_given_true + other.prob_given_true, 1) == 1
            and round(self.prob_given_false + other.prob_given_false, 1) == 1
        )

    @property
    def template(self) -> str | None:
        """Not all observations have templates and we want to get template strings."""
        if self.value_template is not None:
            return self.value_template.template
        return None
