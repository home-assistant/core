"""Coordinator for Actron Air integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from actron_neo_api import (
    ActronAirAPI,
    ActronAirAPIError,
    ActronAirAuthError,
    ActronAirPeripheral,
    ActronAirStatus,
)
from actron_neo_api.models.system import ActronAirSystemInfo
from actron_neo_api.rt import RealtimeConnectionEvent, RealtimeConnectionState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

POLL_INTERVAL = timedelta(seconds=30)
PUSH_POLL_INTERVAL = timedelta(minutes=5)
ERROR_NO_SYSTEMS_FOUND = "no_systems_found"
ERROR_UNKNOWN = "unknown_error"

# States in which the transport is not delivering updates. CONNECTING is excluded
# because the transport reports it before every connection attempt, including the
# first one, which has no missed updates to recover.
OUTAGE_STATES = (
    RealtimeConnectionState.RECONNECTING,
    RealtimeConnectionState.DISCONNECTED,
    RealtimeConnectionState.ERROR,
)


@dataclass
class ActronAirRuntimeData:
    """Runtime data for the Actron Air integration."""

    api: ActronAirAPI
    system_coordinators: dict[str, ActronAirSystemCoordinator]


type ActronAirConfigEntry = ConfigEntry[ActronAirRuntimeData]


class ActronAirSystemCoordinator(DataUpdateCoordinator[ActronAirStatus]):
    """System coordinator for Actron Air integration."""

    config_entry: ActronAirConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ActronAirConfigEntry,
        api: ActronAirAPI,
        system: ActronAirSystemInfo,
        *,
        push_enabled: bool,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Actron Air Status",
            update_interval=PUSH_POLL_INTERVAL if push_enabled else POLL_INTERVAL,
            config_entry=entry,
        )
        self.system = system
        self.serial_number = system.serial
        self.api = api
        self.push_enabled = push_enabled
        self.status = self.api.state_manager.get_status(self.serial_number)
        self.peripherals: dict[str, ActronAirPeripheral] = {}
        self._missed_updates = False

    @override
    async def _async_setup(self) -> None:
        """Subscribe to realtime updates for this system."""
        if not self.push_enabled:
            return

        self.config_entry.async_on_unload(
            self.api.subscribe_system_updates(
                self.serial_number, self._handle_push_update
            )
        )
        self.config_entry.async_on_unload(
            self.api.subscribe_connection_state(self._handle_connection_event)
        )

    @callback
    def _handle_push_update(self, status: ActronAirStatus) -> None:
        """Handle a realtime status update for this system."""
        self.status = status
        self.peripherals = {
            peripheral.serial_number: peripheral for peripheral in status.peripherals
        }
        self.async_set_updated_data(status)

    async def _handle_connection_event(self, event: RealtimeConnectionEvent) -> None:
        """Resync after the realtime transport recovers from an outage.

        The outage is latched rather than read from `event.previous_state`: the
        transport reports CONNECTING between RECONNECTING and CONNECTED, so every
        CONNECTED event looks alike regardless of what preceded the attempt.
        """
        if event.state in OUTAGE_STATES:
            self._missed_updates = True
        elif event.state is RealtimeConnectionState.CONNECTED and self._missed_updates:
            self._missed_updates = False
            await self.async_request_refresh()

    @override
    async def _async_update_data(self) -> ActronAirStatus:
        """Fetch updates and merge incremental changes into the full state."""
        try:
            await self.api.update_status()
        except ActronAirAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except ActronAirAPIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": repr(err)},
            ) from err

        status = self.api.state_manager.get_status(self.serial_number)
        if status is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": "Status not available"},
            )
        self.status = status
        self.peripherals = {
            peripheral.serial_number: peripheral for peripheral in status.peripherals
        }
        return self.status
