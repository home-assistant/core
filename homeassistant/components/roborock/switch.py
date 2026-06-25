"""Support for Roborock switch."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, override

from roborock.devices.traits.b01 import Q10PropertiesApi
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.common import RoborockSwitchBase
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
)
from .entity import (
    RoborockCoordinatedEntityA01,
    RoborockCoordinatedEntityB01Q10,
    RoborockEntityV1,
)

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


@dataclass(frozen=True, kw_only=True)
class RoborockSwitchDescriptionA01(SwitchEntityDescription):
    """Class to describe a Roborock A01 switch entity."""

    data_protocol: RoborockDyadDataProtocol | RoborockZeoProtocol


@dataclass(frozen=True, kw_only=True)
class RoborockSwitchDescriptionQ10(SwitchEntityDescription):
    """Class to describe a Roborock Q10 switch entity."""

    trait: Callable[[Q10PropertiesApi], RoborockSwitchBase | None]


A01_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionA01] = [
    RoborockSwitchDescriptionA01(
        key="sound_setting",
        data_protocol=RoborockZeoProtocol.SOUND_SET,
        translation_key="sound_setting",
        entity_category=EntityCategory.CONFIG,
    ),
]


Q10_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionQ10] = [
    RoborockSwitchDescriptionQ10(
        key="do_not_disturb",
        translation_key="dnd_switch",
        entity_category=EntityCategory.CONFIG,
        trait=lambda traits: getattr(traits, "do_not_disturb", None),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    coordinators = config_entry.runtime_data

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add entities for a specific coordinator."""
        entities: list[SwitchEntity] = []
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            entities.extend(
                RoborockSwitch(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator,
                    description,
                    trait,
                )
                for description in SWITCH_DESCRIPTIONS
                if (trait := description.trait(coordinator.properties_api)) is not None
            )
        elif isinstance(coordinator, RoborockDataUpdateCoordinatorA01):
            entities.extend(
                RoborockSwitchA01(
                    coordinator,
                    description,
                )
                for description in A01_SWITCH_DESCRIPTIONS
                if description.data_protocol in coordinator.request_protocols
            )
        elif isinstance(coordinator, RoborockB01Q10UpdateCoordinator):
            entities.extend(
                RoborockSwitchQ10(
                    coordinator,
                    description,
                    trait,
                )
                for description in Q10_SWITCH_DESCRIPTIONS
                if (trait := description.trait(coordinator.api)) is not None
            )
        async_add_entities(entities)

    for coordinator in coordinators.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
    )


class RoborockSwitch(RoborockEntityV1, SwitchEntity):
    """A class to toggle Roborock device functionality with a coordinator."""

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

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._trait.disable()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @override
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
    @override
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._trait.is_on


class RoborockSwitchA01(RoborockCoordinatedEntityA01, SwitchEntity):
    """A class to let you turn functionality on Roborock A01 devices on and off."""

    entity_description: RoborockSwitchDescriptionA01

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinatorA01,
        description: RoborockSwitchDescriptionA01,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(f"{description.key}_{coordinator.duid_slug}", coordinator)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self.coordinator.api.set_value(  # type: ignore[attr-defined]
                self.entity_description.data_protocol, 0
            )
            await self.coordinator.async_request_refresh()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.coordinator.api.set_value(  # type: ignore[attr-defined]
                self.entity_description.data_protocol, 1
            )
            await self.coordinator.async_request_refresh()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        status = self.coordinator.data.get(self.entity_description.data_protocol)
        if status is None:
            return None
        return bool(status)


class RoborockSwitchQ10(RoborockCoordinatedEntityB01Q10, SwitchEntity):
    """A class to toggle a setting on a Roborock Q10 device."""

    entity_description: RoborockSwitchDescriptionQ10
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockB01Q10UpdateCoordinator,
        description: RoborockSwitchDescriptionQ10,
        trait: RoborockSwitchBase,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._trait = trait
        super().__init__(f"{description.key}_{coordinator.duid_slug}", coordinator)

    @override
    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based state updates."""
        await super().async_added_to_hass()
        if hasattr(self._trait, "add_update_listener"):
            self.async_on_remove(
                self._trait.add_update_listener(self.async_write_ha_state)
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._trait.disable()
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @override
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
    @override
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._trait.is_on
