"""Switch platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyliebherrhomeapi import (
    LiebherrConnectionError,
    LiebherrTimeoutError,
    ToggleControl,
    ZonePosition,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

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
class LiebherrZoneSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Liebherr zone-based switch entity."""

    control_name: str
    set_fn: Callable[[LiebherrCoordinator, int, bool], Awaitable[None]]


@dataclass(frozen=True, kw_only=True)
class LiebherrDeviceSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Liebherr device-wide switch entity."""

    control_name: str
    set_fn: Callable[[LiebherrCoordinator, bool], Awaitable[None]]


type LiebherrSwitchEntityDescription = (
    LiebherrZoneSwitchEntityDescription | LiebherrDeviceSwitchEntityDescription
)

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
    entities: list[LiebherrSwitch] = []

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
                    LiebherrSwitch(
                        coordinator=coordinator,
                        description=desc,
                        zone_id=control.zone_id,
                        has_multiple_zones=has_multiple_zones,
                    )
                )

            # Device-wide switches (Party Mode, Night Mode)
            elif device_desc := DEVICE_SWITCH_TYPES.get(control.name):
                entities.append(
                    LiebherrSwitch(
                        coordinator=coordinator,
                        description=device_desc,
                    )
                )

    async_add_entities(entities)


class LiebherrSwitch(LiebherrEntity, SwitchEntity):
    """Representation of a Liebherr switch."""

    entity_description: LiebherrSwitchEntityDescription
    _cancel_refresh: CALLBACK_TYPE | None = None

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        description: LiebherrSwitchEntityDescription,
        zone_id: int | None = None,
        has_multiple_zones: bool = False,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_id = zone_id

        if zone_id is not None:
            self._attr_unique_id = (
                f"{coordinator.device_id}_{description.key}_{zone_id}"
            )
            # Add zone suffix only for multi-zone devices
            if has_multiple_zones:
                temp_controls = coordinator.data.get_temperature_controls()
                if (
                    (tc := temp_controls.get(zone_id))
                    and isinstance(tc.zone_position, ZonePosition)
                    and (zone_key := ZONE_POSITION_MAP.get(tc.zone_position))
                ):
                    self._attr_translation_key = (
                        f"{description.translation_key}_{zone_key}"
                    )
        else:
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
        return self._toggle_control.value  # type: ignore[union-attr]

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

    async def _async_set_value(self, value: bool) -> None:
        """Set the switch value."""
        try:
            if isinstance(self.entity_description, LiebherrZoneSwitchEntityDescription):
                assert self._zone_id is not None
                await self.entity_description.set_fn(
                    self.coordinator, self._zone_id, value
                )
            else:
                await self.entity_description.set_fn(self.coordinator, value)
        except (LiebherrConnectionError, LiebherrTimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_failed",
            ) from err

        # Optimistically update local state to avoid flicker from API delay
        if control := self._toggle_control:
            control.value = value
        self.async_write_ha_state()

        # Cancel any pending refresh and schedule a new one
        if self._cancel_refresh:
            self._cancel_refresh()
        self._cancel_refresh = async_call_later(
            self.hass, REFRESH_DELAY, self._async_refresh_callback
        )

    @callback
    def _async_refresh_callback(self, _now: Any) -> None:
        """Request a coordinator refresh after a delay."""
        self._cancel_refresh = None
        self.hass.async_create_task(
            self.coordinator.async_request_refresh(),
            eager_start=False,
        )
