"""Support for System Bridge switches."""

from typing import TYPE_CHECKING, Any, override

from systembridgeconnector.models.modules.displays import DisplayPowerState

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AUDIO_INPUT
from .coordinator import SystemBridgeConfigEntry
from .entity import (
    SystemBridgeAudioDeviceEntity,
    SystemBridgeDisplayEntity,
    async_add_new_audio_devices,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge switches based on a config entry."""
    coordinator = entry.runtime_data
    known_displays: set[str] = set()

    @callback
    def _async_add_new_displays() -> None:
        """Add power switches for displays not seen before."""
        # Only displays that report a power state can be turned on or off
        new_displays = [
            display.id
            for display in coordinator.data.displays
            if display.power_state is not None and display.id not in known_displays
        ]
        if not new_displays:
            return
        known_displays.update(new_displays)
        async_add_entities(
            SystemBridgeDisplayPowerSwitch(
                coordinator, entry.data[CONF_PORT], "power", display_id
            )
            for display_id in new_displays
        )

    _async_add_new_displays()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_displays))

    async_add_new_audio_devices(
        entry,
        AUDIO_INPUT,
        lambda devices: async_add_entities(
            SystemBridgeAudioInputMuteSwitch(
                coordinator,
                entry.data[CONF_PORT],
                f"audio_input_{device.id}_mute",
                AUDIO_INPUT,
                device,
            )
            for device in devices
        ),
        lambda device: device.muted is not None,
    )


class SystemBridgeDisplayPowerSwitch(SystemBridgeDisplayEntity, SwitchEntity):
    """Define a System Bridge display power switch."""

    _attr_translation_key = "display_power"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the display is on, rather than in standby, suspended or off."""
        if (display := self._display) is None or display.power_state is None:
            return None
        return display.power_state == DisplayPowerState.ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the display on."""
        await self._async_display_control(power_state=DisplayPowerState.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the display off."""
        await self._async_display_control(power_state=DisplayPowerState.OFF)


class SystemBridgeAudioInputMuteSwitch(SystemBridgeAudioDeviceEntity, SwitchEntity):
    """Define a System Bridge audio input mute switch."""

    _attr_translation_key = "audio_input_mute"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return if the input is muted."""
        if (device := self._device) is None:
            return None
        return device.muted

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the input."""
        await self._async_set_muted(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the input."""
        await self._async_set_muted(False)

    async def _async_set_muted(self, muted: bool) -> None:
        """Set the input's mute state."""
        device = self._device
        if TYPE_CHECKING:
            assert device is not None
        await self._async_audio_control(device, muted=muted)
