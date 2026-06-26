"""Support for Imou switch controls."""

from typing import Any, override

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_STATE, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

PARAM_MOTION_DETECT = "motion_detect"
PARAM_HEADER_DETECT = "header_detect"
PARAM_WHITE_LIGHT = "white_light"
PARAM_CLOSE_CAMERA = "close_camera"
PARAM_AB_ALARM_SOUND = "ab_alarm_sound"
PARAM_AUDIO_ENCODE_CONTROL = "audio_encode_control"
PARAM_LIGHT = "light"
PARAM_PLUG_SWITCH = "switch"

SWITCH_TYPES = (
    PARAM_MOTION_DETECT,
    PARAM_HEADER_DETECT,
    PARAM_WHITE_LIGHT,
    PARAM_CLOSE_CAMERA,
    PARAM_AB_ALARM_SOUND,
    PARAM_AUDIO_ENCODE_CONTROL,
    PARAM_LIGHT,
    PARAM_PLUG_SWITCH,
)

SWITCH_DEVICE_CLASS: dict[str, SwitchDeviceClass] = {
    PARAM_LIGHT: SwitchDeviceClass.SWITCH,
    PARAM_PLUG_SWITCH: SwitchDeviceClass.SWITCH,
}


def _iter_switches(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[str, ImouHaDevice]]:
    """Return (switch_type, device) pairs for supported switches."""
    return [
        (switch_type, device)
        for device in coordinator.devices
        for switch_type in device.switches
        if switch_type in SWITCH_TYPES
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou switch entities."""
    coordinator = entry.runtime_data

    def _add_switches(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSwitch(coordinator, switch_type, device)
            for switch_type, device in _iter_switches(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_add_switches)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_switches in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_switches)

    entry.async_on_unload(_remove_new_device_callback)
    _add_switches(coordinator.devices)


class ImouSwitch(ImouEntity, SwitchEntity):
    """Imou switch entity."""

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou switch entity."""
        super().__init__(coordinator, entity_type, device)
        if device_class := SWITCH_DEVICE_CLASS.get(entity_type):
            self._attr_device_class = device_class

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.device.switches[self._entity_type][PARAM_STATE]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_switch_operation(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_switch_operation(False)

    async def _async_switch_operation(self, enable: bool) -> None:
        """Call the vendor library to change switch state."""
        try:
            await self.coordinator.device_manager.async_switch_operation(
                self.device,
                self._entity_type,
                enable,
            )
            self.device.switches[self._entity_type][PARAM_STATE] = enable
            self.async_write_ha_state()
        except ImouException as e:
            raise HomeAssistantError(str(e)) from e
