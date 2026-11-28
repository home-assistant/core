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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink fans based on a config entry."""
    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]

    if device.api.type in DOMAINS_AND_TYPES[Platform.FAN]:
        async_add_entities([BroadlinkLifaAirPurifierFan(device)])


class BroadlinkLifaAirPurifierFan(BroadlinkEntity, FanEntity):
    """Representation of the LIFAair purifier fan."""

    _MAX_FAN_SPEED = 121

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
        mode.name.lower()
        for mode in (
            lifaair.FanMode.AUTO,
            lifaair.FanMode.NIGHT,
            lifaair.FanMode.TURBO,
            lifaair.FanMode.ANTI_ALLERGY,
        )
    ]
    _attr_speed_count = 100

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the LIFAair fan entity."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id

    @staticmethod
    def _fan_percentage_to_speed(percentage: int) -> int:
        return round(BroadlinkLifaAirPurifierFan._MAX_FAN_SPEED * percentage / 100)

    @staticmethod
    def _fan_speed_to_percentage(fan_speed: int) -> int:
        return round(100 * fan_speed / BroadlinkLifaAirPurifierFan._MAX_FAN_SPEED)

    @staticmethod
    def _fan_mode_to_name(fan_mode: lifaair.FanMode) -> str:
        return fan_mode.name.lower()

    @staticmethod
    def _fan_name_to_mode(fan_mode_name: str) -> lifaair.FanMode:
        return lifaair.FanMode[fan_mode_name.upper()]

    @callback
    @override
    def _update_state(self, data: dict[str, Any]) -> None:
        """Update fan state."""
        self._attr_available = bool(data["purifier_online"])
        if not self._attr_available:
            # None is reserved for the Bluetooth purifier being offline.
            self._attr_preset_mode = None
            self._attr_percentage = None
            return

        fan_mode = data["fan_mode"]
        fan_speed = data["fan_speed"]
        percentage = (
            self._fan_speed_to_percentage(fan_speed) if fan_speed is not None else None
        )
        if fan_mode is None or fan_mode == lifaair.FanMode.OFF:
            self._attr_preset_mode = None
            self._attr_percentage = 0
            return
        if fan_mode == lifaair.FanMode.MANUAL:
            self._attr_preset_mode = None
            self._attr_percentage = percentage
            return
        preset_name = self._fan_mode_to_name(fan_mode)
        if not self.preset_modes or preset_name not in self.preset_modes:
            # UNKNOWN or any mode the entity does not expose as a preset.
            self._attr_preset_mode = None
            self._attr_percentage = percentage
            return
        self._attr_preset_mode = preset_name
        self._attr_percentage = percentage

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        fan_mode = self._fan_name_to_mode(preset_mode)
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
        fan_speed = self._fan_percentage_to_speed(percentage)
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
        if self.is_on:
            return False
        await self._async_request(self._device.api.set_fan_mode, lifaair.FanMode.AUTO)
        return True

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
