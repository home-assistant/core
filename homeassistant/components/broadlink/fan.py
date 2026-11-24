"""Support for Broadlink air purifiers."""

from collections.abc import Awaitable, Callable
from typing import Any, override

from broadlink_async.purifier import lifaair

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADLINK_DATA, DOMAINS_AND_TYPES
from .device import BroadlinkDevice
from .entity import BroadlinkEntity

MAX_FAN_SPEED = 121


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink fans based on a config entry."""
    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]

    if device.api.type in DOMAINS_AND_TYPES[Platform.FAN]:
        async_add_entities([LifaAirPurifierFan(device)])


def _fan_percentage_to_speed(percentage: int) -> int:
    return round(MAX_FAN_SPEED * percentage / 100)


def _fan_speed_to_percentage(fan_speed: int) -> int:
    return round(100 * fan_speed / MAX_FAN_SPEED)


def _fan_mode_to_name(fan_mode: lifaair.FanMode) -> str:
    return fan_mode.name.lower()


def _fan_name_to_mode(fan_mode_name: str) -> lifaair.FanMode:
    return lifaair.FanMode[fan_mode_name.upper()]


class LifaAirPurifierFan(BroadlinkEntity, FanEntity):
    """Representation of a Broadlink LIFAair fan entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "lifaair"
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [
        _fan_mode_to_name(mode)
        for mode in lifaair.FanMode
        if mode not in (lifaair.FanMode.OFF, lifaair.FanMode.UNKNOWN)
    ]
    _attr_speed_count = 100

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the LIFAair fan entity."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id

    @callback
    @override
    def _update_state(self, data: dict[str, Any]) -> None:
        """Update fan state."""
        fan_mode = data["fan_mode"]
        self._attr_available = fan_mode is not None
        if fan_mode is None:
            return
        if fan_mode == lifaair.FanMode.OFF:
            self._attr_preset_mode = None
            self._attr_percentage = None
            return
        self._attr_preset_mode = _fan_mode_to_name(fan_mode)
        fan_speed = data["fan_speed"]
        self._attr_percentage = (
            _fan_speed_to_percentage(fan_speed) if fan_speed is not None else None
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        fan_mode = _fan_name_to_mode(preset_mode)
        if fan_mode == lifaair.FanMode.MANUAL:
            # The API enters MANUAL mode by setting a speed, not by setting a mode.
            await self.async_set_percentage(self.percentage or 50)
        else:
            was_set_to_auto = await self._async_turn_on_if_needed()
            if not (was_set_to_auto and fan_mode == lifaair.FanMode.AUTO):
                await self._async_request(self._device.api.set_fan_mode, fan_mode)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self._async_turn_on_if_needed()
        fan_speed = _fan_percentage_to_speed(percentage)
        await self._async_request(self._device.api.set_fan_speed, fan_speed)

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan using AUTO mode when no mode or speed is given."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            await self._async_turn_on_if_needed()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._async_request(self._device.api.set_fan_mode, lifaair.FanMode.OFF)

    async def _async_turn_on_if_needed(self) -> bool:
        # Set AUTO before commands that are rejected while the fan is off.
        if self.preset_mode is None:
            await self._async_request(
                self._device.api.set_fan_mode, lifaair.FanMode.AUTO
            )
            return True
        return False

    async def _async_request(
        self,
        function: Callable[..., Awaitable[dict[str, Any]]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # All state setting api calls also return current updated state,
        # so we use it to immediately update HA state without waiting for next refresh.
        data = await self._device.async_request(function, *args, **kwargs)
        self._coordinator.async_set_updated_data(data)
