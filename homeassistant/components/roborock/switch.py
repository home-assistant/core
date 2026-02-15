"""Support for Roborock switch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from roborock.data.b01_q10.b01_q10_code_mappings import B01_Q10_DP
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.common import RoborockSwitchBase
from roborock.exceptions import RoborockException

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityB01, RoborockEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockSwitchDescription(SwitchEntityDescription):
    """Class to describe a Roborock switch entity."""

    trait: Callable[[PropertiesApi], RoborockSwitchBase | None]

    # If it is a dock entity
    is_dock_entity: bool = False


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        trait=lambda traits: traits.child_lock,
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        is_dock_entity=True,
    ),
    RoborockSwitchDescription(
        trait=lambda traits: traits.flow_led_status,
        key="status_indicator",
        translation_key="status_indicator",
        entity_category=EntityCategory.CONFIG,
        is_dock_entity=True,
    ),
    RoborockSwitchDescription(
        trait=lambda traits: traits.dnd,
        key="dnd_switch",
        translation_key="dnd_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        trait=lambda traits: traits.valley_electricity_timer,
        key="off_peak_switch",
        translation_key="off_peak_switch",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    coordinators = config_entry.runtime_data

    # V1 switches
    entities: list[RoborockSwitch | RoborockQ10Switch] = [
        RoborockSwitch(
            f"{description.key}_{coordinator.duid_slug}",
            coordinator,
            description,
            trait,
        )
        for coordinator in coordinators.v1
        for description in SWITCH_DESCRIPTIONS
        if (trait := description.trait(coordinator.properties_api)) is not None
    ]

    # Q10 switches (only for RoborockB01Q10UpdateCoordinator)
    entities.extend(
        RoborockQ10Switch(
            f"child_lock_{coordinator.duid_slug}",
            coordinator,
        )
        for coordinator in coordinators.b01
        if isinstance(coordinator, RoborockB01Q10UpdateCoordinator)
    )

    async_add_entities(entities)


class RoborockSwitch(RoborockEntityV1, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSwitchDescription,
        trait: RoborockSwitchBase,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description
        super().__init__(
            unique_id,
            (
                coordinator.device_info
                if not entity_description.is_dock_entity
                else coordinator.dock_device_info
            ),
            coordinator.properties_api.command,
        )
        self._trait = trait

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._trait.disable()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._trait.enable()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._trait.is_on


class RoborockQ10Switch(RoborockCoordinatedEntityB01, SwitchEntity):
    """Roborock Q10 switch entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "child_lock"
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockB01Q10UpdateCoordinator,
    ) -> None:
        """Initialize the Q10 child lock switch."""
        super().__init__(unique_id, coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return True if child lock is on."""
        if isinstance(self.coordinator.data, dict):
            value = self.coordinator.data.get(B01_Q10_DP.CHILD_LOCK)
            if value is not None:
                return bool(value)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on child lock."""
        try:
            await self.coordinator.api.command.send(B01_Q10_DP.CHILD_LOCK, 1)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off child lock."""
        try:
            await self.coordinator.api.command.send(B01_Q10_DP.CHILD_LOCK, 0)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
        await self.coordinator.async_refresh()
