"""Demo platform that offers a fake button entity."""

from __future__ import annotations

from kasa import Device, Feature

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
    _description_for_feature,
    _entities_for_device_and_its_children,
)
from .models import TPLinkData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device,
        feature_type=Feature.Action,
        entity_class=Button,
        coordinator=parent_coordinator,
    )

    async_add_entities(entities)


class Button(CoordinatedTPLinkEntity, ButtonEntity):
    """Representation of a TPLink button entity."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
        self.entity_description = _description_for_feature(
            ButtonEntityDescription, feature
        )

    async def async_press(self) -> None:
        """Execute action."""
        await self._feature.set_value(True)

    def _async_update_attrs(self):
        """No need to update anything."""
