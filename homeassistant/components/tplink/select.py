"""Support for TPLink select entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from kasa import Device, Feature

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkDataUpdateCoordinator,
    TPLinkFeatureEntityDescription,
    async_refresh_after,
)


@dataclass(frozen=True, kw_only=True)
class TPLinkSelectEntityDescription(
    SelectEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based select entity description."""


# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0

SELECT_DESCRIPTIONS: Final = [
    TPLinkSelectEntityDescription(
        key="light_preset",
    ),
    TPLinkSelectEntityDescription(
        key="alarm_sound",
    ),
    TPLinkSelectEntityDescription(
        key="alarm_volume",
    ),
]

SELECT_DESCRIPTIONS_MAP = {desc.key: desc for desc in SELECT_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device
    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            feature_type=Feature.Type.Choice,
            entity_class=TPLinkSelectEntity,
            descriptions=SELECT_DESCRIPTIONS_MAP,
            platform_domain=SELECT_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkSelectEntity(CoordinatedTPLinkFeatureEntity, SelectEntity):
    """Representation of a tplink select entity."""

    entity_description: TPLinkSelectEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        description: TPLinkFeatureEntityDescription,
        parent: Device | None = None,
    ) -> None:
        """Initialize a select."""
        super().__init__(
            device, coordinator, feature=feature, description=description, parent=parent
        )
        self._attr_options = cast(list, self._feature.choices)

    @async_refresh_after
    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        await self._feature.set_value(option)

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_current_option = cast(str | None, self._feature.value)
        return True
