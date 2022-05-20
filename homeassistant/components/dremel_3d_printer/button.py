"""Support for Dremel 3D Printer buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Dremel3DPrinterDataUpdateCoordinator, Dremel3DPrinterDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dremel 3D Printer control buttons."""
    coordinator: Dremel3DPrinterDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    device_id = config_entry.unique_id

    assert device_id is not None

    async_add_entities(
        [
            Dremel3DPrinterResumeJobButton(coordinator, config_entry),
            Dremel3DPrinterPauseJobButton(coordinator, config_entry),
            Dremel3DPrinterStopJobButton(coordinator, config_entry),
        ]
    )


class Dremel3DPrinterButton(Dremel3DPrinterDeviceEntity, ButtonEntity):
    """Represent a Dremel 3D Printer base button."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
        button_type: str,
    ) -> None:
        """Initialize a new Dremel 3D Printer button."""
        super().__init__(coordinator, config_entry)
        self._device_id = config_entry.unique_id
        self._attr_name = f"{button_type}"
        self._attr_unique_id = f"{button_type}-{config_entry.unique_id}"


class Dremel3DPrinterPauseJobButton(Dremel3DPrinterButton):
    """Pause the active job."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer pause button."""
        super().__init__(coordinator, config_entry, "Pause Job")

    async def async_press(self) -> None:
        """Handle the pause button press."""
        if self.coordinator.api.is_unpaused():
            self.coordinator.api.pause_print()
        else:
            raise InvalidPrinterState("Printer is not printing")


class Dremel3DPrinterResumeJobButton(Dremel3DPrinterButton):
    """Resume the active job."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer resume button."""
        super().__init__(coordinator, config_entry, "Resume Job")

    async def async_press(self) -> None:
        """Handle the resume button press."""
        if self.coordinator.api.is_paused():
            self.coordinator.api.resume_print()
        else:
            raise InvalidPrinterState("Printer is not currently paused")


class Dremel3DPrinterStopJobButton(Dremel3DPrinterButton):
    """Stop the active job."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer stop button."""
        super().__init__(coordinator, config_entry, "Stop Job")

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.api.is_printing():
            self.coordinator.api.stop_print()


class InvalidPrinterState(HomeAssistantError):
    """Service attempted in invalid state."""
