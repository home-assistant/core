"""Support for TPLink button entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from kasa import Device, Feature

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkFeatureEntityDescription,
    _description_for_feature,
    _entities_for_device_and_its_children,
)


@dataclass(frozen=True, kw_only=True)
class TPLinkButtonEntityDescription(
    ButtonEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based button entity description."""


BUTTON_DESCRIPTIONS: Final = [
    TPLinkButtonEntityDescription(
        key="test_alarm",
    ),
    TPLinkButtonEntityDescription(
        key="stop_alarm",
    ),
]

BUTTON_DESCRIPTIONS_MAP = {desc.key: desc for desc in BUTTON_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Action,
        entity_class=Button,
        child_coordinators=children_coordinators,
    )
    async_add_entities(entities)


class Button(CoordinatedTPLinkFeatureEntity, ButtonEntity):
    """Representation of a TPLink button entity."""

    entity_description: TPLinkButtonEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the button."""
        description = _description_for_feature(
            TPLinkButtonEntityDescription, feature, BUTTON_DESCRIPTIONS_MAP
        )
        super().__init__(
            device, coordinator, description=description, feature=feature, parent=parent
        )
        self._async_call_update_attrs()

    async def async_press(self) -> None:
        """Execute action."""
        await self._feature.set_value(True)

    def _async_update_attrs(self) -> None:
        """No need to update anything."""
