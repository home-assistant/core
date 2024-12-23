"""Support for TPLink number entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final, cast

from kasa import Device, Feature

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkDataUpdateCoordinator,
    TPLinkFeatureEntityDescription,
    async_refresh_after,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TPLinkNumberEntityDescription(
    NumberEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based sensor entity description."""


NUMBER_DESCRIPTIONS: Final = (
    TPLinkNumberEntityDescription(
        key="smooth_transition_on",
        mode=NumberMode.BOX,
    ),
    TPLinkNumberEntityDescription(
        key="smooth_transition_off",
        mode=NumberMode.BOX,
    ),
    TPLinkNumberEntityDescription(
        key="auto_off_minutes",
        mode=NumberMode.BOX,
    ),
    TPLinkNumberEntityDescription(
        key="temperature_offset",
        mode=NumberMode.BOX,
    ),
    TPLinkNumberEntityDescription(
        key="pan_step",
        mode=NumberMode.BOX,
    ),
    TPLinkNumberEntityDescription(
        key="tilt_step",
        mode=NumberMode.BOX,
    ),
)

NUMBER_DESCRIPTIONS_MAP = {desc.key: desc for desc in NUMBER_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    device = parent_coordinator.device
    entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
        hass=hass,
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Number,
        entity_class=TPLinkNumberEntity,
        descriptions=NUMBER_DESCRIPTIONS_MAP,
        child_coordinators=children_coordinators,
    )

    async_add_entities(entities)


class TPLinkNumberEntity(CoordinatedTPLinkFeatureEntity, NumberEntity):
    """Representation of a feature-based TPLink sensor."""

    entity_description: TPLinkNumberEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        description: TPLinkFeatureEntityDescription,
        parent: Device | None = None,
    ) -> None:
        """Initialize the a switch."""
        super().__init__(
            device, coordinator, feature=feature, description=description, parent=parent
        )
        self._attr_native_min_value = self._feature.minimum_value
        self._attr_native_max_value = self._feature.maximum_value

    @async_refresh_after
    async def async_set_native_value(self, value: float) -> None:
        """Set feature value."""
        await self._feature.set_value(int(value))

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_native_value = cast(float | None, self._feature.value)
        return True
