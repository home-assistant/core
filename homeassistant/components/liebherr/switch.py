"""Switch platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyliebherrhomeapi import ToggleControl, ZonePosition
from pyliebherrhomeapi.const import (
    CONTROL_NIGHT_MODE,
    CONTROL_PARTY_MODE,
    CONTROL_SUPER_COOL,
    CONTROL_SUPER_FROST,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import ZONE_POSITION_MAP, LiebherrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LiebherrSwitchEntityDescription(SwitchEntityDescription):
    """Base description for Liebherr switch entities."""

    control_name: str


@dataclass(frozen=True, kw_only=True)
class LiebherrZoneSwitchEntityDescription(LiebherrSwitchEntityDescription):
    """Describes a Liebherr zone-based switch entity."""

    set_fn: Callable[[LiebherrCoordinator, int, bool], Awaitable[None]]


@dataclass(frozen=True, kw_only=True)
class LiebherrDeviceSwitchEntityDescription(LiebherrSwitchEntityDescription):
    """Describes a Liebherr device-wide switch entity."""

    set_fn: Callable[[LiebherrCoordinator, bool], Awaitable[None]]


ZONE_SWITCH_TYPES: dict[str, LiebherrZoneSwitchEntityDescription] = {
    CONTROL_SUPER_COOL: LiebherrZoneSwitchEntityDescription(
        key="super_cool",
        translation_key="super_cool",
        control_name=CONTROL_SUPER_COOL,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_super_cool(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            value=value,
        ),
    ),
    CONTROL_SUPER_FROST: LiebherrZoneSwitchEntityDescription(
        key="super_frost",
        translation_key="super_frost",
        control_name=CONTROL_SUPER_FROST,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_super_frost(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            value=value,
        ),
    ),
}

DEVICE_SWITCH_TYPES: dict[str, LiebherrDeviceSwitchEntityDescription] = {
    CONTROL_PARTY_MODE: LiebherrDeviceSwitchEntityDescription(
        key="party_mode",
        translation_key="party_mode",
        control_name=CONTROL_PARTY_MODE,
        set_fn=lambda coordinator, value: coordinator.client.set_party_mode(
            device_id=coordinator.device_id,
            value=value,
        ),
    ),
    CONTROL_NIGHT_MODE: LiebherrDeviceSwitchEntityDescription(
        key="night_mode",
        translation_key="night_mode",
        control_name=CONTROL_NIGHT_MODE,
        set_fn=lambda coordinator, value: coordinator.client.set_night_mode(
            device_id=coordinator.device_id,
            value=value,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr switch entities."""
    entities: list[LiebherrDeviceSwitch | LiebherrZoneSwitch] = []

    for coordinator in entry.runtime_data.values():
        has_multiple_zones = len(coordinator.data.get_temperature_controls()) > 1

        for control in coordinator.data.controls:
            if not isinstance(control, ToggleControl):
                continue

            # Zone-based switches (SuperCool, SuperFrost)
            if control.zone_id is not None and (
                desc := ZONE_SWITCH_TYPES.get(control.name)
            ):
                entities.append(
                    LiebherrZoneSwitch(
                        coordinator=coordinator,
                        description=desc,
                        zone_id=control.zone_id,
                        has_multiple_zones=has_multiple_zones,
                    )
                )

            # Device-wide switches (PartyMode, NightMode)
            elif device_desc := DEVICE_SWITCH_TYPES.get(control.name):
                entities.append(
                    LiebherrDeviceSwitch(
                        coordinator=coordinator,
                        description=device_desc,
                    )
                )

    async_add_entities(entities)


class LiebherrDeviceSwitch(LiebherrEntity, SwitchEntity):
    """Representation of a device-wide Liebherr switch."""

    entity_description: LiebherrSwitchEntityDescription
    _zone_id: int | None = None

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        description: LiebherrSwitchEntityDescription,
    ) -> None:
        """Initialize the device switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def _toggle_control(self) -> ToggleControl | None:
        """Get the toggle control for this entity."""
        for control in self.coordinator.data.controls:
            if (
                isinstance(control, ToggleControl)
                and control.name == self.entity_description.control_name
                and (self._zone_id is None or control.zone_id == self._zone_id)
            ):
                return control
        return None

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if TYPE_CHECKING:
            assert self._toggle_control is not None
        return self._toggle_control.value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._toggle_control is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_value(False)

    async def _async_call_set_fn(self, value: bool) -> None:
        """Call the set function for this switch."""
        if TYPE_CHECKING:
            assert isinstance(
                self.entity_description, LiebherrDeviceSwitchEntityDescription
            )
        await self.entity_description.set_fn(self.coordinator, value)

    async def _async_set_value(self, value: bool) -> None:
        """Set the switch value."""
        await self._async_send_command(self._async_call_set_fn(value))


class LiebherrZoneSwitch(LiebherrDeviceSwitch):
    """Representation of a zone-based Liebherr switch."""

    entity_description: LiebherrZoneSwitchEntityDescription
    _zone_id: int

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        description: LiebherrZoneSwitchEntityDescription,
        zone_id: int,
        has_multiple_zones: bool,
    ) -> None:
        """Initialize the zone switch entity."""
        super().__init__(coordinator, description)
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}_{zone_id}"

        # Add zone suffix only for multi-zone devices
        if has_multiple_zones:
            temp_controls = coordinator.data.get_temperature_controls()
            if (
                (tc := temp_controls.get(zone_id))
                and isinstance(tc.zone_position, ZonePosition)
                and (zone_key := ZONE_POSITION_MAP.get(tc.zone_position))
            ):
                self._attr_translation_key = f"{description.translation_key}_{zone_key}"

    async def _async_call_set_fn(self, value: bool) -> None:
        """Call the set function for this zone switch."""
        await self.entity_description.set_fn(self.coordinator, self._zone_id, value)
