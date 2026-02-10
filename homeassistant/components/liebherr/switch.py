"""Switch platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyliebherrhomeapi import (
    LiebherrConnectionError,
    LiebherrTimeoutError,
    ToggleControl,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import LiebherrEntity, LiebherrZoneEntity

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


ZONE_SWITCH_TYPES: tuple[LiebherrZoneSwitchEntityDescription, ...] = (
    LiebherrZoneSwitchEntityDescription(
        key="supercool",
        translation_key="supercool",
        control_name=CONTROL_SUPERCOOL,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_supercool(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            value=value,
        ),
    ),
    LiebherrZoneSwitchEntityDescription(
        key="superfrost",
        translation_key="superfrost",
        control_name=CONTROL_SUPERFROST,
        set_fn=lambda coordinator, zone_id, value: coordinator.client.set_superfrost(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            value=value,
        ),
    ),
)

DEVICE_SWITCH_TYPES: tuple[LiebherrDeviceSwitchEntityDescription, ...] = (
    LiebherrDeviceSwitchEntityDescription(
        key="party_mode",
        translation_key="party_mode",
        control_name=CONTROL_PARTY_MODE,
        set_fn=lambda coordinator, value: coordinator.client.set_party_mode(
            device_id=coordinator.device_id,
            value=value,
        ),
    ),
    LiebherrDeviceSwitchEntityDescription(
        key="night_mode",
        translation_key="night_mode",
        control_name=CONTROL_NIGHT_MODE,
        set_fn=lambda coordinator, value: coordinator.client.set_night_mode(
            device_id=coordinator.device_id,
            value=value,
        ),
    ),
)


def _get_toggle_by_name(
    coordinator: LiebherrCoordinator, name: str
) -> ToggleControl | None:
    """Get a toggle control by name from the coordinator data."""
    for control in coordinator.data.controls:
        if isinstance(control, ToggleControl) and control.name == name:
            return control
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr switch entities."""
    coordinators = entry.runtime_data
    entities: list[LiebherrZoneSwitch | LiebherrDeviceSwitch] = []

    for coordinator in coordinators.values():
        temp_controls = coordinator.data.get_temperature_controls()
        has_multiple_zones = len(temp_controls) > 1

        for control in coordinator.data.controls:
            if not isinstance(control, ToggleControl):
                continue

            # Zone-based switches (SuperCool, SuperFrost)
            entities.extend(
                LiebherrZoneSwitch(
                    coordinator=coordinator,
                    zone_id=control.zone_id,
                    description=description,
                    has_multiple_zones=has_multiple_zones,
                )
                for description in ZONE_SWITCH_TYPES
                if control.name == description.control_name
                and control.zone_id is not None
            )

            # Device-wide switches (Party Mode, Night Mode)
            entities.extend(
                LiebherrDeviceSwitch(
                    coordinator=coordinator,
                    description=description,
                )
                for description in DEVICE_SWITCH_TYPES
                if control.name == description.control_name
            )

    async_add_entities(entities)


class LiebherrZoneSwitch(LiebherrZoneEntity, SwitchEntity):
    """Representation of a zone-based Liebherr switch."""

    entity_description: LiebherrZoneSwitchEntityDescription

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        zone_id: int,
        description: LiebherrZoneSwitchEntityDescription,
        has_multiple_zones: bool,
    ) -> None:
        """Initialize the zone switch entity."""
        super().__init__(coordinator, zone_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}_{zone_id}"

        # Add zone suffix only for multi-zone devices
        if has_multiple_zones and (zone_key := self._get_zone_translation_key()):
            self._attr_translation_key = f"{description.translation_key}_{zone_key}"

    @property
    def _toggle_control(self) -> ToggleControl | None:
        """Get the toggle control for this entity."""
        return _get_toggle_by_name(
            self.coordinator, self.entity_description.control_name
        )

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
            await self.entity_description.set_fn(self.coordinator, self._zone_id, value)
        except (LiebherrConnectionError, LiebherrTimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_failed",
            ) from err

        # Optimistically update local state to avoid flicker from API delay
        if control := self._toggle_control:
            control.value = value
        self.async_write_ha_state()

        # Schedule a delayed refresh to pick up device-side effects
        async_call_later(self.hass, REFRESH_DELAY, self._async_refresh_callback)

    @callback
    def _async_refresh_callback(self, _now: Any) -> None:
        """Request a coordinator refresh after a delay."""
        self.hass.async_create_task(
            self.coordinator.async_request_refresh(),
            eager_start=False,
        )


class LiebherrDeviceSwitch(LiebherrEntity, SwitchEntity):
    """Representation of a device-wide Liebherr switch."""

    entity_description: LiebherrDeviceSwitchEntityDescription

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        description: LiebherrDeviceSwitchEntityDescription,
    ) -> None:
        """Initialize the device switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def _toggle_control(self) -> ToggleControl | None:
        """Get the toggle control for this entity."""
        return _get_toggle_by_name(
            self.coordinator, self.entity_description.control_name
        )

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

        # Schedule a delayed refresh to pick up device-side effects
        async_call_later(self.hass, REFRESH_DELAY, self._async_refresh_callback)

    @callback
    def _async_refresh_callback(self, _now: Any) -> None:
        """Request a coordinator refresh after a delay."""
        self.hass.async_create_task(
            self.coordinator.async_request_refresh(),
            eager_start=False,
        )
