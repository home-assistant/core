"""Support for Imou button controls."""

from __future__ import annotations

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BUTTON_TYPES,
    PARAM_MUTE,
    PARAM_PTZ_DOWN,
    PARAM_PTZ_LEFT,
    PARAM_PTZ_RIGHT,
    PARAM_PTZ_UP,
    PARAM_RESTART_DEVICE,
)
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1

BUTTON_DESCRIPTIONS: dict[str, ButtonEntityDescription] = {
    PARAM_RESTART_DEVICE: ButtonEntityDescription(
        key=PARAM_RESTART_DEVICE,
        device_class=ButtonDeviceClass.RESTART,
    ),
    PARAM_MUTE: ButtonEntityDescription(key=PARAM_MUTE),
    PARAM_PTZ_UP: ButtonEntityDescription(key=PARAM_PTZ_UP),
    PARAM_PTZ_DOWN: ButtonEntityDescription(key=PARAM_PTZ_DOWN),
    PARAM_PTZ_LEFT: ButtonEntityDescription(key=PARAM_PTZ_LEFT),
    PARAM_PTZ_RIGHT: ButtonEntityDescription(key=PARAM_PTZ_RIGHT),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou button entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ImouButton(coordinator, button_type, device)
        for device in coordinator.devices
        for button_type in device.buttons
        if button_type in BUTTON_TYPES
    )


class ImouButton(ImouEntity, ButtonEntity):
    """Imou button entity."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou button entity."""
        super().__init__(coordinator, entity_type, device)
        self.entity_description = BUTTON_DESCRIPTIONS[entity_type]

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            await self.coordinator.device_manager.async_press_button(
                self._device,
                self._entity_type,
                500,
            )
        except ImouException as e:
            raise HomeAssistantError(e.message) from e
