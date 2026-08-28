"""Switches for the NexBlue integration."""

from collections.abc import Callable
from datetime import datetime
import time
from typing import Any, override

from nexblue_api import NexBlueError

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator

ASSUMED_STATE_SECONDS = 15
COMMAND_REFRESH_DELAYS = (1, 3, 8, 15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NexBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a charging switch for every discovered charger."""
    coordinator = entry.runtime_data
    async_add_entities(
        NexBlueChargingSwitch(coordinator, serial_number)
        for serial_number in coordinator.data
    )


class NexBlueChargingSwitch(
    CoordinatorEntity[NexBlueDataUpdateCoordinator], SwitchEntity
):
    """Control whether a NexBlue charger is actively charging."""

    _attr_has_entity_name = True
    _attr_translation_key = "charging"

    def __init__(
        self,
        coordinator: NexBlueDataUpdateCoordinator,
        serial_number: str,
    ) -> None:
        """Initialize the charging switch."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._assumed_is_on: bool | None = None
        self._assumed_state_expires_at = 0.0
        self._pending_refreshes: set[Callable[[], None]] = set()
        self.async_on_remove(self._cancel_pending_refreshes)
        self._attr_unique_id = f"{serial_number}_charging"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="NexBlue",
            name=serial_number,
            serial_number=serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether this charger is currently reachable."""
        return (
            super().available
            and self.coordinator.data.get(self._serial_number) is not None
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the charger is actively charging."""
        if (
            self._assumed_is_on is not None
            and time.monotonic() < self._assumed_state_expires_at
        ):
            return self._assumed_is_on

        self._assumed_is_on = None
        status = self.coordinator.data.get(self._serial_number)
        if status is None:
            return False
        return status.charging_state == 2

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        await self._async_set_charging(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        await self._async_set_charging(False)

    async def _async_set_charging(self, should_charge: bool) -> None:
        """Send a command, immediately update state, and refresh status."""
        try:
            if should_charge:
                await self.coordinator.client.async_start_charging(self._serial_number)
            else:
                await self.coordinator.client.async_stop_charging(self._serial_number)
        except NexBlueError as err:
            raise HomeAssistantError(str(err)) from err

        self._assumed_is_on = should_charge
        self._assumed_state_expires_at = time.monotonic() + ASSUMED_STATE_SECONDS
        self.async_write_ha_state()
        self._schedule_command_refreshes()
        await self.coordinator.async_refresh()

    def _schedule_command_refreshes(self) -> None:
        """Refresh while cloud and charger state catch up after a command."""

        def _schedule_refresh(delay: int) -> None:
            cancel: Callable[[], None] | None = None

            @callback
            def _request_refresh(_now: datetime) -> None:
                """Request a refresh from the Home Assistant event loop."""
                if cancel is not None:
                    self._pending_refreshes.discard(cancel)
                self.hass.async_create_task(self.coordinator.async_refresh())

            cancel = async_call_later(self.hass, delay, _request_refresh)
            self._pending_refreshes.add(cancel)

        for delay in COMMAND_REFRESH_DELAYS:
            _schedule_refresh(delay)

    def _cancel_pending_refreshes(self) -> None:
        """Cancel refreshes that have not fired when the entity is removed."""
        for cancel in self._pending_refreshes:
            cancel()
        self._pending_refreshes.clear()
