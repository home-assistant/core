"""Support for Imou button controls."""

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BUTTON_TYPES,
    PARAM_RESTART_DEVICE,
    PTZ_BUTTON_TYPES,
    PTZ_MOVE_DURATION_MS,
    imou_device_identifier,
)
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1

BUTTON_DEVICE_CLASS: dict[str, ButtonDeviceClass] = {
    PARAM_RESTART_DEVICE: ButtonDeviceClass.RESTART,
}


def _iter_buttons(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[str, ImouHaDevice]]:
    """Return (button_type, device) pairs for supported buttons."""
    return [
        (button_type, device)
        for device in coordinator.devices
        for button_type in device.buttons
        if button_type in BUTTON_TYPES
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou button entities."""
    coordinator = entry.runtime_data

    def _async_add_buttons(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouButton(coordinator, button_type, device)
            for button_type, device in _iter_buttons(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_async_add_buttons)
    _async_add_buttons(coordinator.devices)


class ImouButton(ImouEntity, ButtonEntity):
    """Imou button entity."""

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou button entity."""
        super().__init__(coordinator, entity_type, device)
        if device_class := BUTTON_DEVICE_CLASS.get(entity_type):
            self._attr_device_class = device_class
            self._attr_translation_key = None

    async def async_press(self) -> None:
        """Handle button press."""
        duration = (
            PTZ_MOVE_DURATION_MS
            if self._entity_type in PTZ_BUTTON_TYPES
            else 0
        )
        try:
            await self.coordinator.device_manager.async_press_button(
                self._device,
                self._entity_type,
                duration,
            )
        except ImouException as e:
            raise HomeAssistantError(e.message) from e
