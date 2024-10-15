"""Support for TPLink switch entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from kasa import Feature

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkFeatureEntityDescription,
    async_refresh_after,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TPLinkSwitchEntityDescription(
    SwitchEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based sensor entity description."""


SWITCH_DESCRIPTIONS: tuple[TPLinkSwitchEntityDescription, ...] = (
    TPLinkSwitchEntityDescription(
        key="state",
    ),
    TPLinkSwitchEntityDescription(
        key="led",
    ),
    TPLinkSwitchEntityDescription(
        key="auto_update_enabled",
    ),
    TPLinkSwitchEntityDescription(
        key="auto_off_enabled",
    ),
    TPLinkSwitchEntityDescription(
        key="smooth_transitions",
    ),
    TPLinkSwitchEntityDescription(
        key="fan_sleep_mode",
    ),
)

SWITCH_DESCRIPTIONS_MAP = {desc.key: desc for desc in SWITCH_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
        hass=hass,
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Switch,
        entity_class=TPLinkSwitch,
        descriptions=SWITCH_DESCRIPTIONS_MAP,
    )

    async_add_entities(entities)


class TPLinkSwitch(CoordinatedTPLinkFeatureEntity, SwitchEntity):
    """Representation of a feature-based TPLink switch."""

    entity_description: TPLinkSwitchEntityDescription

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._feature.set_value(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._feature.set_value(False)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
