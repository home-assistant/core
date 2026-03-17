"""Data models for the Photoptimizer integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class OptimizationBucket:
    """Single aggregated timestep prepared for the optimizer."""

    start: datetime
    price: float
    pv: float
    load: float

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for coordinator data."""
        return asdict(self)


@dataclass(slots=True)
class OptimizationInputs:
    """Aggregated inputs passed from the coordinator to the EMHASS client."""

    timeline: list[OptimizationBucket]
    battery_soc: float
    raw_forecast_solar: Any | None = None

    @property
    def prediction_horizon(self) -> int:
        """Return the number of timesteps sent to EMHASS."""
        return len(self.timeline)

    @property
    def optimization_time_step_minutes(self) -> int:
        """Infer the optimization step from the aggregated timeline."""
        if len(self.timeline) < 2:
            return 60

        return int(
            (self.timeline[1].start - self.timeline[0].start).total_seconds() // 60
        )


@dataclass(slots=True)
class PublishedEntityState:
    """Snapshot of an EMHASS-published Home Assistant entity."""

    entity_id: str
    state: str | None
    attributes: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for coordinator data."""
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
        }


@dataclass(slots=True)
class EmhassExecutionResult:
    """Complete result of one EMHASS optimization and publish cycle."""

    runtimeparams: dict[str, Any]
    optimization_response: dict[str, Any]
    publish_response: dict[str, Any]
    published_entities: dict[str, PublishedEntityState]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for coordinator data."""
        return {
            "runtimeparams": self.runtimeparams,
            "optimization_response": self.optimization_response,
            "publish_response": self.publish_response,
            "published_entities": {
                key: entity.as_dict() for key, entity in self.published_entities.items()
            },
        }
