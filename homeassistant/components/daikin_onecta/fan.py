"""Support for Daikin air purifiers."""

from collections.abc import Awaitable, Callable
from math import ceil
from typing import Any, override

from daikin_onecta.air_purification import AirPurificationClient
from daikin_onecta.models import AirPurification

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import FANMODE_FIXED
from .coordinator import OnectaDataUpdateCoordinator
from .entity import DaikinManagementPointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin air-purifier fan entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    entities: list[DaikinAirPurifier] = []
    for device in (coordinator.data or {}).values():
        entities.extend(
            DaikinAirPurifier(device, management_point.embedded_id, coordinator)
            for management_point in device.device.management_points_by_type(
                "climateControl"
            )
            if (
                management_point.air_purification is not None
                and (power := management_point.air_purification.power) is not None
                and power.settable
            )
        )
    async_add_entities(entities)


class DaikinAirPurifier(DaikinManagementPointEntity, FanEntity):
    """Representation of a Daikin air purifier."""

    _attr_has_entity_name = True

    def __init__(
        self, device, embedded_id: str, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Initialize the air purifier."""
        super().__init__(device, coordinator, embedded_id, "climateControl")
        self._attr_unique_id = f"{device.id}_{embedded_id}_air_purifier"
        self._update_state()

    def _air_purification(self) -> AirPurification | None:
        """Return the typed air-purification state view."""
        management_point = self._device.management_point(self._embedded_id)
        return (
            management_point.air_purification if management_point is not None else None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the actual Daikin power state, independent of selected mode."""
        purification = self._air_purification()
        return (
            purification.power.value == "on"
            if purification and purification.power
            else None
        )

    async def _async_execute_air_purification_command(
        self,
        command: Callable[[AirPurificationClient], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a typed air-purification command."""
        await self._async_execute_command(
            lambda client: command(
                client.air_purification(self._device.id, self._embedded_id)
            ),
            translation_key,
        )

    def _fixed_speed_range(self) -> tuple[float, float] | None:
        """Return the current mode's writable fixed-speed range."""
        purification = self._air_purification()
        operation = purification.fan_operation() if purification is not None else None
        fixed = (
            operation.fan_speed.modes.get(FANMODE_FIXED)
            if operation and operation.fan_speed and operation.fan_speed.modes
            else None
        )
        if (
            fixed is None
            or not fixed.settable
            or fixed.min_value is None
            or fixed.max_value is None
        ):
            return None
        return float(fixed.min_value), float(fixed.max_value)

    def _fixed_speed_count(self) -> int | None:
        """Return the number of discrete writable fixed speeds."""
        purification = self._air_purification()
        operation = purification.fan_operation() if purification is not None else None
        fixed = (
            operation.fan_speed.modes.get(FANMODE_FIXED)
            if operation and operation.fan_speed and operation.fan_speed.modes
            else None
        )
        if (
            fixed is None
            or fixed.min_value is None
            or fixed.max_value is None
            or fixed.step_value is None
            or fixed.step_value <= 0
        ):
            return None
        return int((fixed.max_value - fixed.min_value) / fixed.step_value) + 1

    def _update_state(self) -> None:
        """Refresh entity state from typed purifier data."""
        purification = self._air_purification()
        if purification is None:
            return
        power = purification.power
        self._attr_is_on = power is not None and power.value == "on"
        self._attr_preset_mode = (
            purification.mode.value if purification.mode is not None else None
        )
        self._attr_preset_modes = purification.modes
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if purification.modes:
            features |= FanEntityFeature.PRESET_MODE
        if (speed_range := self._fixed_speed_range()) is not None:
            features |= FanEntityFeature.SET_SPEED
            operation = purification.fan_operation()
            assert (
                operation is not None
                and operation.fan_speed is not None
                and operation.fan_speed.modes is not None
            )
            self._attr_percentage = ranged_value_to_percentage(
                speed_range, int(operation.fan_speed.modes[FANMODE_FIXED].value)
            )
            self._attr_speed_count = self._fixed_speed_count() or 100
        else:
            self._attr_percentage = None
            self._attr_speed_count = 100
        self._attr_supported_features = features

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the air purifier."""
        if not self.is_on:
            await self._async_execute_air_purification_command(
                lambda purifier: purifier.set_power(True),
                "air_purifier_turn_on_failed",
            )
            purification = self._air_purification()
            if purification is not None and purification.power is not None:
                purification.power.value = "on"
            self._update_state()
            self.coordinator.async_update_listeners()
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is not None:
            await self.async_set_percentage(percentage)

    @override
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the air purifier."""
        if not self.is_on:
            return
        await self._async_execute_air_purification_command(
            lambda purifier: purifier.set_power(False),
            "air_purifier_turn_off_failed",
        )
        purification = self._air_purification()
        if purification is not None and purification.power is not None:
            purification.power.value = "off"
        self._update_state()
        self.coordinator.async_update_listeners()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a native Daikin air-purification mode."""
        purification = self._air_purification()
        if purification is None or preset_mode not in purification.modes:
            self._raise_command_failed("air_purifier_set_mode_failed")
        if preset_mode == self.preset_mode:
            return
        await self._async_execute_air_purification_command(
            lambda purifier: purifier.set_mode(preset_mode),
            "air_purifier_set_mode_failed",
        )
        if purification.mode is not None:
            purification.mode.value = preset_mode
        self._update_state()
        self.coordinator.async_update_listeners()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the current mode's fixed fan speed."""
        if percentage == 0:
            await self.async_turn_off()
            return
        purification = self._air_purification()
        if purification is None or purification.mode is None:
            self._raise_command_failed("air_purifier_set_percentage_failed")
        if self._fixed_speed_range() is None and "manualFan" in purification.modes:
            await self.async_set_preset_mode("manualFan")
        speed_range = self._fixed_speed_range()
        if speed_range is None:
            self._raise_command_failed("air_purifier_set_percentage_failed")
        mode = purification.mode
        assert mode is not None
        speed = ceil(percentage_to_ranged_value(speed_range, percentage))
        await self._async_execute_air_purification_command(
            lambda purifier: purifier.set_fixed_fan_speed(mode.value, speed),
            "air_purifier_set_percentage_failed",
        )
        operation = purification.fan_operation()
        assert (
            operation is not None
            and operation.fan_speed is not None
            and operation.fan_speed.modes is not None
        )
        operation.fan_speed.modes[FANMODE_FIXED].value = speed
        self._update_state()
        self.coordinator.async_update_listeners()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated coordinator data."""
        self._update_state()
        self.async_write_ha_state()
