"""Helpers to deal with bayesian observations."""
from __future__ import annotations

from homeassistant.helpers.template import Template


class Observation:
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
