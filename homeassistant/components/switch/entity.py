"""Base entity for the Switch platform."""

from typing import override

from propcache.api import cached_property

from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription

from .const import SwitchDeviceClass


class SwitchEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes switch entities."""

    device_class: SwitchDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
}


class SwitchEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for switch entities."""

    entity_description: SwitchEntityDescription
    _attr_device_class: SwitchDeviceClass | None

    @cached_property
    @override
    def device_class(self) -> SwitchDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None
