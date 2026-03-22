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

_Q10_SWITCH_DPS_LISTENERS: dict[
    int,
    list[Callable[[dict[B01_Q10_DP, Any]], None]],
] = {}


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

    dp_code: B01_Q10_DP


Q10_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionQ10] = [
    RoborockSwitchDescriptionQ10(
        key="child_lock",
        dp_code=B01_Q10_DP.CHILD_LOCK,
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescriptionQ10(
        key="dnd_switch",
        dp_code=B01_Q10_DP.NOT_DISTURB,
        translation_key="dnd_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescriptionQ10(
        key="auto_empty",
        dp_code=B01_Q10_DP.DUST_SWITCH,
        translation_key="auto_empty",
        entity_category=EntityCategory.CONFIG,
    ),
]


A01_SWITCH_DESCRIPTIONS: list[RoborockSwitchDescriptionA01] = [
    RoborockSwitchDescriptionA01(
        key="sound_setting",
        data_protocol=RoborockZeoProtocol.SOUND_SET,
        translation_key="sound_setting",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    entities = [
        *[
            RoborockSwitch(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator,
                description,
                trait,
            )
            for coordinator in config_entry.runtime_data.v1
            for description in SWITCH_DESCRIPTIONS
            if (trait := description.trait(coordinator.properties_api)) is not None
        ],
        *[
            RoborockQ10Switch(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator,
                description,
            )
            for coordinator in config_entry.runtime_data.b01_q10
            for description in Q10_SWITCH_DESCRIPTIONS
        ],
        *[
            RoborockSwitchA01(
                coordinator,
                description,
            )
            for coordinator in config_entry.runtime_data.a01
            for description in A01_SWITCH_DESCRIPTIONS
            if description.data_protocol in coordinator.request_protocols
        ],
    ]
    for coordinator in config_entry.runtime_data.b01_q10:
        await coordinator.async_refresh()
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


class RoborockQ10Switch(RoborockCoordinatedEntityB01Q10, SwitchEntity):
    """Roborock Q10 switch entity."""

    entity_description: RoborockSwitchDescriptionQ10
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockB01Q10UpdateCoordinator,
        entity_description: RoborockSwitchDescriptionQ10,
    ) -> None:
        """Initialize the Q10 switch."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator)
        self._dp_code = entity_description.dp_code
        self._is_on: bool | None = None
        self._dps_listener = self._async_handle_dps_update
        self._register_dps_listener()

    def _register_dps_listener(self) -> None:
        """Register a listener for raw DPS updates from the status trait."""
        coordinator_id = id(self.coordinator)
        listeners = _Q10_SWITCH_DPS_LISTENERS.setdefault(coordinator_id, [])
        listeners.append(self._dps_listener)

        if len(listeners) > 1:
            return

        original_update_from_dps = self.coordinator.api.status.update_from_dps

        def update_from_dps(decoded_dps: dict[B01_Q10_DP, Any]) -> None:
            """Forward raw DPS updates to listeners before trait conversion."""
            for listener in list(_Q10_SWITCH_DPS_LISTENERS.get(coordinator_id, [])):
                listener(decoded_dps)
            original_update_from_dps(decoded_dps)

        setattr(self.coordinator.api.status, "update_from_dps", update_from_dps)

    async def async_will_remove_from_hass(self) -> None:
        """Remove DPS listener."""
        coordinator_id = id(self.coordinator)
        listeners = _Q10_SWITCH_DPS_LISTENERS.get(coordinator_id)
        if listeners and self._dps_listener in listeners:
            listeners.remove(self._dps_listener)
            if not listeners:
                _Q10_SWITCH_DPS_LISTENERS.pop(coordinator_id, None)
        await super().async_will_remove_from_hass()

    def _async_handle_dps_update(self, decoded_dps: dict[B01_Q10_DP, Any]) -> None:
        """Handle a raw DPS update."""
        if self._dp_code not in decoded_dps:
            return

        self._is_on = bool(decoded_dps[self._dp_code])
        if self.hass:
            self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return True if switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.coordinator.api.command.send(self._dp_code, 1)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
        self._is_on = True
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self.coordinator.api.command.send(self._dp_code, 0)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
        self._is_on = False
        await self.coordinator.async_refresh()


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
