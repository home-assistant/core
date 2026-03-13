"""Support for Imou button controls."""

from __future__ import annotations

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_RESTART_DEVICE, PARAM_STATE, PARAM_STATUS
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 1


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
    )


class ImouButton(ImouEntity, ButtonEntity):
    """Imou button entity."""

    _attr_device_class: ButtonDeviceClass | None = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou button entity."""
        super().__init__(coordinator, entity_type, device)
        if entity_type != PARAM_RESTART_DEVICE:
            self._attr_device_class = None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        if not super().available:
            return False
        if self._entity_type == PARAM_STATUS:
            return True
        if PARAM_STATUS not in self._device.sensors:
            return False
        return (
            self._device.sensors[PARAM_STATUS][PARAM_STATE]
            != DeviceStatus.OFFLINE.value
        )

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
