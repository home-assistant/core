"""Support for Imou button controls."""

from typing import override

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PTZ_MOVE_DURATION_MS, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1
# Button types
PARAM_RESTART_DEVICE = "restart_device"
PARAM_MUTE = "mute"
PARAM_PTZ_UP = "ptz_up"
PARAM_PTZ_DOWN = "ptz_down"
PARAM_PTZ_LEFT = "ptz_left"
PARAM_PTZ_RIGHT = "ptz_right"

PTZ_BUTTON_TYPES = (
    PARAM_PTZ_UP,
    PARAM_PTZ_DOWN,
    PARAM_PTZ_LEFT,
    PARAM_PTZ_RIGHT,
)

BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key=PARAM_RESTART_DEVICE,
        device_class=ButtonDeviceClass.RESTART,
    ),
    ButtonEntityDescription(
        key=PARAM_MUTE,
        translation_key=PARAM_MUTE,
    ),
    ButtonEntityDescription(
        key=PARAM_PTZ_UP,
        translation_key=PARAM_PTZ_UP,
    ),
    ButtonEntityDescription(
        key=PARAM_PTZ_DOWN,
        translation_key=PARAM_PTZ_DOWN,
    ),
    ButtonEntityDescription(
        key=PARAM_PTZ_LEFT,
        translation_key=PARAM_PTZ_LEFT,
    ),
    ButtonEntityDescription(
        key=PARAM_PTZ_RIGHT,
        translation_key=PARAM_PTZ_RIGHT,
    ),
)


def _iter_buttons(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[ButtonEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for supported buttons."""
    return [
        (description, device)
        for device in coordinator.devices
        for description in BUTTON_TYPES
        if description.key in device.buttons
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou button entities."""
    coordinator = entry.runtime_data

    def _add_buttons(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouButton(coordinator, description, device)
            for description, device in _iter_buttons(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_add_buttons)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_buttons in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_buttons)

    entry.async_on_unload(_remove_new_device_callback)
    _add_buttons(coordinator.devices)


class ImouButton(ImouEntity, ButtonEntity):
    """Imou button entity."""

    entity_description: ButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Handle button press."""
        duration = PTZ_MOVE_DURATION_MS if self._entity_type in PTZ_BUTTON_TYPES else 0
        try:
            await self.coordinator.device_manager.async_press_button(
                self.device,
                self._entity_type,
                duration,
            )
        except ImouException as e:
            raise HomeAssistantError(str(e)) from e
