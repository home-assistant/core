"""Button platform for the APsystems Lake_6 integration."""

from typing import Any, override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Lake6ConfigEntry, Lake6Coordinator
from .entity import Lake6Entity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Lake6ConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lake_6 button platform."""
    coordinator = config_entry.runtime_data.coordinator
    add_entities(
        [
            Lake6ManualControlApplyButton(coordinator),
            Lake6ManualControlInterruptButton(coordinator),
        ]
    )


class Lake6ManualControlApplyButton(Lake6Entity, ButtonEntity):
    """Send the staged manual control request to the device.

    The mode, wattage and duration boxes only stage values; this is the single
    place that writes them, which keeps a half-filled request from restarting
    the window on every keystroke. The staged values survive a rejection, so the
    user can retry without typing them again.
    """

    _attr_translation_key = "manual_control_apply"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the dispatch button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_manual_control_apply"

    @property
    @override
    def available(self) -> bool:
        """Require a complete staged request.

        The panel shows a row only while its entity is available, so an
        incomplete request hides the button instead of inviting a press that
        could only fail. Standby needs no wattage (§4.7) and is complete
        without one.
        """
        control = self.coordinator.manual_control
        return (
            super().available
            and control.mode is not None
            and control.signed_power is not None
            and control.duration is not None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the staged request and the last outcome.

        The device clears `MI1` as soon as the run ends, so `last_sent_at` is
        the only place the previous request stays readable afterwards.
        """
        control = self.coordinator.manual_control
        sent_at = control.last_sent_at
        return {
            "staged_mode": control.mode,
            "staged_power": control.power,
            "staged_duration": control.duration,
            "last_sent_at": sent_at.isoformat() if sent_at else None,
            "last_error": control.last_error,
        }

    @override
    async def async_press(self) -> None:
        """Post the staged request and verify the device started it."""
        await self.coordinator.async_apply_manual_control()


class Lake6ManualControlInterruptButton(Lake6Entity, ButtonEntity):
    """Stop the one-time run and hand control back to the long-term mode.

    A one-time run has the device's highest priority and overrides the long-term
    mode for its whole window, so the only way out before the window expires is
    to clear it explicitly. The button is unavailable while nothing runs, which
    also keeps a stray press from writing `mode="0"` for no reason.
    """

    _attr_translation_key = "manual_control_interrupt"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the interrupt button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_manual_control_interrupt"

    @property
    @override
    def available(self) -> bool:
        """Only offered while the device reports a running window."""
        return super().available and self.coordinator.data.control_panel.active

    @override
    async def async_press(self) -> None:
        """Clear the one-time run."""
        await self.coordinator.async_interrupt_manual_control()
