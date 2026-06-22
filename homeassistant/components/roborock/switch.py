"""Support for Roborock switch."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.devices.traits.b01 import Q10PropertiesApi
from roborock.devices.traits.common import TraitUpdateListener
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.common import RoborockSwitchBase
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol

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


A01_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionA01] = [
    RoborockSwitchDescriptionA01(
        key="sound_setting",
        data_protocol=RoborockZeoProtocol.SOUND_SET,
        translation_key="sound_setting",
        entity_category=EntityCategory.CONFIG,
    ),
]


@dataclass(frozen=True, kw_only=True)
class RoborockSwitchDescriptionQ10(SwitchEntityDescription):
    """Class to describe a Roborock Q10 switch entity."""

    # Current state, or ``None`` for write-only switches with no read-back.
    is_on_fn: Callable[[Q10PropertiesApi], bool | None]
    enable_fn: Callable[[Q10PropertiesApi], Coroutine[Any, Any, None]]
    disable_fn: Callable[[Q10PropertiesApi], Coroutine[Any, Any, None]]
    # Trait to listen to for pushed state changes, or ``None`` for write-only.
    listen_fn: Callable[[Q10PropertiesApi], TraitUpdateListener] | None = None
    # Write-only switches (no read-back) report an assumed state.
    assumed_state: bool = False


Q10_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionQ10] = [
    RoborockSwitchDescriptionQ10(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda api: api.child_lock.is_on,
        enable_fn=lambda api: api.child_lock.enable(),
        disable_fn=lambda api: api.child_lock.disable(),
        listen_fn=lambda api: api.child_lock,
    ),
    RoborockSwitchDescriptionQ10(
        key="do_not_disturb",
        translation_key="do_not_disturb",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda api: api.do_not_disturb.is_on,
        enable_fn=lambda api: api.do_not_disturb.enable(),
        disable_fn=lambda api: api.do_not_disturb.disable(),
        listen_fn=lambda api: api.do_not_disturb,
    ),
    RoborockSwitchDescriptionQ10(
        key="dust_collection",
        translation_key="dust_collection",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda api: api.dust_collection.is_on,
        enable_fn=lambda api: api.dust_collection.enable(),
        disable_fn=lambda api: api.dust_collection.disable(),
        listen_fn=lambda api: api.dust_collection,
    ),
    RoborockSwitchDescriptionQ10(
        key="button_light",
        translation_key="button_light",
        entity_category=EntityCategory.CONFIG,
        # The button light is write-only; the device does not report its state.
        is_on_fn=lambda api: None,
        enable_fn=lambda api: api.button_light.enable(),
        disable_fn=lambda api: api.button_light.disable(),
        assumed_state=True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    # V1 switches - using trait pattern from HEAD
    async_add_entities(
        [
            RoborockSwitch(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator,
                description,
                trait,
            )
            for coordinator in config_entry.runtime_data.v1
            for description in SWITCH_DESCRIPTIONS
            if (trait := description.trait(coordinator.properties_api)) is not None
        ]
    )

    # A01 switches
    async_add_entities(
        RoborockSwitchA01(
            coordinator,
            description,
        )
        for coordinator in config_entry.runtime_data.a01
        for description in A01_SWITCH_DESCRIPTIONS
        if description.data_protocol in coordinator.request_protocols
    )

    # Q10 switches
    async_add_entities(
        RoborockSwitchQ10(coordinator, description)
        for coordinator in config_entry.runtime_data.b01_q10
        for description in Q10_SWITCH_DESCRIPTIONS
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
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        status = self.coordinator.data.get(self.entity_description.data_protocol)
        if status is None:
            return None
        return bool(status)


class RoborockSwitchQ10(RoborockCoordinatedEntityB01Q10, SwitchEntity):
    """A class to toggle a setting on a Roborock Q10 (B01/ss07) device."""

    entity_description: RoborockSwitchDescriptionQ10
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockB01Q10UpdateCoordinator,
        description: RoborockSwitchDescriptionQ10,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        self._attr_assumed_state = description.assumed_state
        super().__init__(f"{description.key}_{coordinator.duid_slug}", coordinator)

    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based state updates."""
        await super().async_added_to_hass()
        if (listen_fn := self.entity_description.listen_fn) is not None:
            self.async_on_remove(
                listen_fn(self.coordinator.api).add_update_listener(
                    self.async_write_ha_state
                )
            )

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on, or None if write-only."""
        return self.entity_description.is_on_fn(self.coordinator.api)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_toggle(self.entity_description.enable_fn)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_toggle(self.entity_description.disable_fn)

    async def _async_toggle(
        self, action: Callable[[Q10PropertiesApi], Coroutine[Any, Any, None]]
    ) -> None:
        try:
            await action(self.coordinator.api)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"command": self.entity_description.key},
            ) from err
