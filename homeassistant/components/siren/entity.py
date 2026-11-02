"""Base entity for the Siren platform."""

from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription

from .const import SirenEntityCapabilityAttribute, SirenEntityFeature


class SirenEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes siren entities."""

    available_tones: list[int | str] | dict[int, str] | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "available_tones",
    "supported_features",
}


class SirenEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a siren device."""

    _entity_component_unrecorded_attributes = frozenset(
        {SirenEntityCapabilityAttribute.AVAILABLE_TONES}
    )

    entity_description: SirenEntityDescription
    _attr_available_tones: list[int | str] | dict[int, str] | None
    _attr_supported_features: SirenEntityFeature = SirenEntityFeature(0)

    @final
    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        if (
            self.supported_features & SirenEntityFeature.TONES
            and self.available_tones is not None
        ):
            return {
                SirenEntityCapabilityAttribute.AVAILABLE_TONES: self.available_tones
            }

        return None

    @cached_property
    def available_tones(self) -> list[int | str] | dict[int, str] | None:
        """Return a list of available tones.

        Requires SirenEntityFeature.TONES.
        """
        if hasattr(self, "_attr_available_tones"):
            return self._attr_available_tones
        if hasattr(self, "entity_description"):
            return self.entity_description.available_tones
        return None

    @cached_property
    @override
    def supported_features(self) -> SirenEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features
