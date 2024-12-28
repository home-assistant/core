"""Ecovacs switch module."""

from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetEnable
from deebot_client.events import EnableEvent

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcovacsConfigEntry
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)
from .util import get_supported_entitites


@dataclass(kw_only=True, frozen=True)
class EcovacsSwitchEntityDescription(
    SwitchEntityDescription,
    EcovacsCapabilityEntityDescription[CapabilitySetEnable],
):
    """Ecovacs switch entity description."""


ENTITY_DESCRIPTIONS: tuple[EcovacsSwitchEntityDescription, ...] = (
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.advanced_mode,
        key="advanced_mode",
        translation_key="advanced_mode",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.clean.continuous,
        key="continuous_cleaning",
        translation_key="continuous_cleaning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.carpet_auto_fan_boost,
        key="carpet_auto_fan_boost",
        translation_key="carpet_auto_fan_boost",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.clean.preference,
        key="clean_preference",
        translation_key="clean_preference",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.true_detect,
        key="true_detect",
        translation_key="true_detect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.border_switch,
        key="border_switch",
        translation_key="border_switch",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.child_lock,
        key="child_lock",
        translation_key="child_lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.moveup_warning,
        key="move_up_warning",
        translation_key="move_up_warning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.cross_map_border_warning,
        key="cross_map_border_warning",
        translation_key="cross_map_border_warning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.safe_protect,
        key="safe_protect",
        translation_key="safe_protect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity] = get_supported_entitites(
        controller, EcovacsSwitchEntity, ENTITY_DESCRIPTIONS
    )
    if entities:
        async_add_entities(entities)


class EcovacsSwitchEntity(
    EcovacsDescriptionEntity[CapabilitySetEnable],
    SwitchEntity,
):
    """Ecovacs switch entity."""

    entity_description: EcovacsSwitchEntityDescription

    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EnableEvent) -> None:
            self._attr_is_on = event.enable
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._device.execute_command(self._capability.set(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._device.execute_command(self._capability.set(False))
