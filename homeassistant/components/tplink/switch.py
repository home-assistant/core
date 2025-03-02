"""Support for TPLink switch entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, cast

from kasa import Feature

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    """Base class for a TPLink feature based switch entity description."""


# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0

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
    TPLinkSwitchEntityDescription(
        key="child_lock",
    ),
    TPLinkSwitchEntityDescription(
        key="pir_enabled",
    ),
    TPLinkSwitchEntityDescription(
        key="motion_detection",
    ),
    TPLinkSwitchEntityDescription(
        key="person_detection",
    ),
    TPLinkSwitchEntityDescription(
        key="tamper_detection",
    ),
    TPLinkSwitchEntityDescription(
        key="baby_cry_detection",
    ),
    TPLinkSwitchEntityDescription(
        key="carpet_boost",
    ),
)

SWITCH_DESCRIPTIONS_MAP = {desc.key: desc for desc in SWITCH_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
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
            feature_type=Feature.Switch,
            entity_class=TPLinkSwitch,
            descriptions=SWITCH_DESCRIPTIONS_MAP,
            platform_domain=SWITCH_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


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
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_is_on = cast(bool | None, self._feature.value)
        return True
