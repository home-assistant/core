"""Support for SwitchBee light."""

from __future__ import annotations

from typing import Any

from switchbee.api import SwitchBeeDeviceOfflineError, SwitchBeeError
from switchbee.device import ApiStateCommand, DeviceType, SwitchBeeDimmer

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator
from .entity import SwitchBeeDeviceEntity

MAX_BRIGHTNESS = 255


def _hass_brightness_to_switchbee(value: int) -> int:
    """Convert hass brightness to SwitchBee."""
    sb_brightness = int(100 * value / MAX_BRIGHTNESS)
    # SwitchBee maximum brightness is 99
    return sb_brightness if sb_brightness != 100 else 99


def _switchbee_brightness_to_hass(value: int) -> int:
    """Convert SwitchBee brightness to hass."""
    if value == 99:
        value = 100
    return round(value * MAX_BRIGHTNESS / 100)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SwitchBee light."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SwitchBeeLightEntity(switchbee_device, coordinator)
        for switchbee_device in coordinator.data.values()
        if switchbee_device.type == DeviceType.Dimmer
    )


class SwitchBeeLightEntity(SwitchBeeDeviceEntity[SwitchBeeDimmer], LightEntity):
    """Representation of a SwitchBee light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        device: SwitchBeeDimmer,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the SwitchBee light."""
        super().__init__(device, coordinator)
        self._attr_is_on = False
        self._attr_brightness = 0

        self._update_attrs_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs_from_coordinator()
        super()._handle_coordinator_update()

    def _update_attrs_from_coordinator(self) -> None:

        coordinator_device = self._get_coordinator_device()
        brightness = coordinator_device.brightness

        # module is offline
        if brightness == -1:
            self._check_if_became_offline()
            return

        self._check_if_became_online()

        self._attr_is_on = bool(brightness != 0)

        # 1-99 is the only valid SwitchBee brightness range
        if 0 < brightness < 100:
            self._attr_brightness = _switchbee_brightness_to_hass(brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to light."""
        if ATTR_BRIGHTNESS in kwargs:
            state: int | str = _hass_brightness_to_switchbee(kwargs[ATTR_BRIGHTNESS])
        else:
            state = ApiStateCommand.ON
            if self.brightness:
                state = _hass_brightness_to_switchbee(self.brightness)

        try:
            await self.coordinator.api.set_state(self._device.id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            raise HomeAssistantError(
                f"Failed to set {self.name} state {state}, {str(exp)}"
            ) from exp

        if not isinstance(state, int):
            # We just turned the light on, still don't know the last brightness known the Central Unit (yet)
            # the brightness will be learned and updated in the next coordinator refresh
            return

        # update the coordinator data manually we already know the Central Unit brightness data for this light
        self._get_coordinator_device().brightness = state
        self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off SwitchBee light."""
        try:
            await self.coordinator.api.set_state(self._device.id, ApiStateCommand.OFF)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            raise HomeAssistantError(
                f"Failed to turn off {self._attr_name}, {str(exp)}"
            ) from exp

        # update the coordinator manually
        self._get_coordinator_device().brightness = 0
        self.coordinator.async_set_updated_data(self.coordinator.data)
