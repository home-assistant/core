"""HA entity models."""

from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class DomikaHaEntity(DataClassJSONMixin):
    """Base homeassistant entity state model."""

    entity_id: str
    time_updated: float
    attributes: dict[str, str]
