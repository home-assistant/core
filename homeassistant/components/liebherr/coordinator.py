"""DataUpdateCoordinator for Liebherr integration."""

import asyncio
from dataclasses import dataclass, field, replace
import logging
from typing import override

from pyliebherrhomeapi import (
    DeviceControl,
    DeviceState,
    LiebherrAuthenticationError,
    LiebherrClient,
    LiebherrConnectionError,
    LiebherrNotFoundError,
    LiebherrPreconditionFailedError,
    LiebherrTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LiebherrData:
    """Runtime data for the Liebherr integration."""

    client: LiebherrClient
    coordinators: dict[str, LiebherrCoordinator] = field(default_factory=dict)


type LiebherrConfigEntry = ConfigEntry[LiebherrData]


class LiebherrCoordinator(DataUpdateCoordinator[DeviceState]):
    """Class to manage Liebherr device state via SSE push updates."""

    config_entry: LiebherrConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LiebherrConfigEntry,
        client: LiebherrClient,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{device_id}",
            config_entry=config_entry,
        )
        self.client = client
        self.device_id = device_id
        self._stream_task: asyncio.Task[None] | None = None
        # First event after each (re)connect carries the full control set;
        # subsequent events are deltas that get merged into cached state.
        self._replace_next_event = True

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator by validating device access."""
        try:
            await self.client.get_device(self.device_id)
        except LiebherrAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except LiebherrConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_connection_error",
                translation_placeholders={"device_id": self.device_id},
            ) from err

    @override
    async def _async_update_data(self) -> DeviceState:
        """Fetch the initial device state.

        Called once by ``async_config_entry_first_refresh`` to seed
        ``self.data`` before the SSE stream starts. After startup, all
        updates arrive via ``_async_run_stream``.
        """
        try:
            return await self.client.get_device_state(self.device_id)
        except LiebherrAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_expired",
            ) from err
        except LiebherrTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_timeout_error",
                translation_placeholders={"device_id": self.device_id},
            ) from err
        except LiebherrConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_communication_error",
                translation_placeholders={"device_id": self.device_id},
            ) from err

    @callback
    def async_start_stream(self) -> None:
        """Start the SSE stream background task."""
        if self._stream_task is not None:
            return
        self._mark_unavailable()
        self._stream_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_run_stream(),
            name=f"{DOMAIN}_stream_{self.device_id}",
        )

    async def _async_run_stream(self) -> None:
        """Consume the SSE stream and merge control deltas into state.

        ``stream_controls_forever`` reconnects internally on recoverable
        errors (connection drops, timeouts, 5xx). Only non-recoverable
        errors (auth, not-found, precondition) propagate here.
        """
        try:
            async for controls in self.client.stream_controls_forever(
                self.device_id,
                on_connect=self._handle_stream_connected,
                on_disconnect=self._handle_stream_disconnected,
            ):
                self._apply_controls(controls)
        except LiebherrAuthenticationError:
            self._mark_unavailable()
            _LOGGER.debug("SSE stream auth failed for %s; starting reauth", self.name)
            self.config_entry.async_start_reauth(self.hass)
        except (LiebherrNotFoundError, LiebherrPreconditionFailedError) as err:
            _LOGGER.warning("SSE stream for device %s stopped: %s", self.device_id, err)
            self._mark_unavailable()

    @override
    async def async_shutdown(self) -> None:
        """Cancel the SSE stream task and shut down the coordinator."""
        if self._stream_task is not None:
            self._stream_task.cancel()
            self._stream_task = None
        await super().async_shutdown()

    def _apply_controls(self, controls: list[DeviceControl]) -> None:
        """Apply a control update: replace on (re)connect, merge otherwise."""
        assert self.data is not None
        if self._replace_next_event:
            self._replace_next_event = False
            new_state = replace(self.data, controls=list(controls))
        else:
            merged: dict[tuple[type[DeviceControl], str, int | None], DeviceControl] = {
                (
                    type(control),
                    control.name,
                    getattr(control, "zone_id", None),
                ): control
                for control in self.data.controls
            }
            for control in controls:
                key = (type(control), control.name, getattr(control, "zone_id", None))
                merged[key] = control
            new_state = replace(self.data, controls=list(merged.values()))
        self.async_set_updated_data(new_state)

    @callback
    def _handle_stream_connected(self) -> None:
        """Handle SSE (re)connect: next event carries the full state."""
        self._replace_next_event = True

    @callback
    def _handle_stream_disconnected(self) -> None:
        """Handle SSE disconnect: mark entities unavailable."""
        self._mark_unavailable()

    @callback
    def _mark_unavailable(self) -> None:
        """Mark the coordinator as unavailable and notify listeners."""
        if not self.last_update_success:
            return
        self.last_update_success = False
        self.async_update_listeners()
