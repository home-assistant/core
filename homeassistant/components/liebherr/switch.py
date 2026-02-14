"""Switch platform for Liebherr integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyliebherrhomeapi import (
    LiebherrConnectionError,
    LiebherrTimeoutError,
    ToggleControl,
    ZonePosition,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import ZONE_POSITION_MAP, LiebherrEntity

PARALLEL_UPDATES = 1
REFRESH_DELAY = 5

# Control names from the API
CONTROL_SUPERCOOL = "supercool"
CONTROL_SUPERFROST = "superfrost"
CONTROL_PARTY_MODE = "partymode"
CONTROL_NIGHT_MODE = "nightmode"


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
    CONTROL_SUPERCOOL: LiebherrZoneSwitchEntityDescription(
        key="supercool",
        translation_key="supercool",
        control_name=CONTROL_SUPERCOOL,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_supercool(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            value=value,
        ),
    ),
    CONTROL_SUPERFROST: LiebherrZoneSwitchEntityDescription(
        key="superfrost",
        translation_key="superfrost",
        control_name=CONTROL_SUPERFROST,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_superfrost(
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

            # Device-wide switches (Party Mode, Night Mode)
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
    _optimistic_state: bool | None = None

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
        if self._optimistic_state is not None:
            return self._optimistic_state
        if TYPE_CHECKING:
            assert self._toggle_control is not None
        return self._toggle_control.value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()

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
        try:
            await self._async_call_set_fn(value)
        except (LiebherrConnectionError, LiebherrTimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        # Track expected state locally to avoid mutating shared coordinator data
        self._optimistic_state = value
        self.async_write_ha_state()

        await asyncio.sleep(REFRESH_DELAY)
        await self.coordinator.async_request_refresh()


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
