"""Support for SwitchBee light."""

from __future__ import annotations

import logging
from typing import Any, cast

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

_LOGGER = logging.getLogger(__name__)


def _brightness_hass_to_switchbee(value: int) -> int:
    """Convert hass brightness to SwitchBee."""
    sb_brightness = int(100 * value / MAX_BRIGHTNESS)
    # SwitchBee maximum brightness is 99
    return sb_brightness if sb_brightness != 100 else 99


def _brightness_switchbee_to_hass(value: int) -> int:
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
    """Representation of an SwitchBee light."""

    def __init__(
        self,
        device: SwitchBeeDimmer,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the SwitchBee light."""
        super().__init__(device, coordinator)
        self._attr_is_on = False
        self._is_online = True
        self._attr_brightness: int = 0
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_available = True

        self._update_attrs_from_coordinator()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_online and super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs_from_coordinator()
        super()._handle_coordinator_update()

    def _update_attrs_from_coordinator(self) -> None:
        async def async_refresh_state() -> None:
            """Refresh the device state in the Central Unit.

            This function addresses issue of a device that came online back but still report
            unavailable state (-1).
            Such device (offline device) will keep reporting unavailable state (-1)
            until it has been actuated by the user (state changed to on/off).

            With this code we keep trying setting dummy state for the device
            in order for it to start reporting its real state back (assuming it came back online)

            """

            try:
                await self.coordinator.api.set_state(self._device.id, "dummy")
            except SwitchBeeDeviceOfflineError:
                return
            except SwitchBeeError:
                return

        coordinator_device = cast(
            SwitchBeeDimmer, self.coordinator.data[self._device.id]
        )
        brightness: int = coordinator_device.brightness

        # module is offline
        if brightness == -1:
            # This specific call will refresh the state of the device in the CU
            self.hass.async_create_task(async_refresh_state())

            # if the device was online (now offline), log message and mark it as Unavailable
            if self._is_online:
                _LOGGER.warning(
                    "%s light is not responding, check the status in the SwitchBee mobile app",
                    self.name,
                )
                self._is_online = False

            return

        # check if the device was offline (now online) and bring it back
        if not self._is_online:
            _LOGGER.info(
                "%s light is now responding",
                self.name,
            )
            self._is_online = True

        self._attr_is_on = bool(brightness != 0)

        # 1-99 is the only valid SwitchBee brightness range
        if 0 < brightness < 100:
            self._attr_brightness = _brightness_switchbee_to_hass(brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to light."""
        if ATTR_BRIGHTNESS in kwargs:
            state: int | str = _brightness_hass_to_switchbee(kwargs[ATTR_BRIGHTNESS])
        else:
            state = ApiStateCommand.ON
            if self.brightness:
                state = _brightness_hass_to_switchbee(self.brightness)

        try:
            await self.coordinator.api.set_state(self._device.id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            raise HomeAssistantError(
                f"Failed to set {self._attr_name} state {state}, {str(exp)}"
            ) from exp

        else:
            # update the coordinator data manually if already know the Central Unit brightness data for this light
            if isinstance(state, int):
                cast(
                    SwitchBeeDimmer, self.coordinator.data[self._device.id]
                ).brightness = state
                self.coordinator.async_set_updated_data(self.coordinator.data)
                return

            # the brightness will be learned and updated in the next coordinator refresh

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off SwitchBee light."""
        try:
            await self.coordinator.api.set_state(self._device.id, ApiStateCommand.OFF)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            raise HomeAssistantError(
                f"Failed to turn off {self._attr_name}, {str(exp)}"
            ) from exp

        else:
            # update the coordinator manually
            cast(SwitchBeeDimmer, self.coordinator.data[self._device.id]).brightness = 0
            self.coordinator.async_set_updated_data(self.coordinator.data)
