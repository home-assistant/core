"""Domika entity models."""

from dataclasses import dataclass

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class DomikaEntitiesList(DataClassJSONMixin):
    """Entities data: name, related ids and capabilities."""

    entities: dict


@dataclass
class DomikaEntityInfo(DataClassJSONMixin):
    """Entity data: name, related ids and capabilities."""

    info: dict
