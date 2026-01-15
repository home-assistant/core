"""Compit entity description."""

from dataclasses import dataclass

from homeassistant.helpers.entity import EntityDescription


@dataclass(frozen=True, kw_only=True)
class CompitEntityDescription(EntityDescription):
    """A class that describes Compit entity."""
