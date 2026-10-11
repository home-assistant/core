"""DataUpdateCoordinator for the Sony TV RS-232 integration.

Sony's RS-232 protocol emits no unsolicited state reports, so the coordinator
polls. Pro Bravia displays answer queries; consumer Bravia TVs are set-only and
ignore them, in which case state only changes when a command is acknowledged
and the coordinator never polls.

Reconnect is owned by the library (serialkit): on a dropped link it fails
in-flight commands, notifies subscribers with ``None``, backs off, reopens the
port, re-runs the connect handshake and notifies again. The coordinator only
reflects those notifications into Home Assistant.
"""

from collections.abc import Callable
from datetime import datetime
from typing import override

from sony_tv_rs232 import (
    CommandTimeoutError,
    ConnectionLostError,
    PowerState,
    ProtocolError,
    SerialKitError,
    SonyTV,
    TVState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, POWER_ON_REFRESH_DELAY, SCAN_INTERVAL

type SonyTVRS232ConfigEntry = ConfigEntry[SonyTVCoordinator]


class SonyTVCoordinator(DataUpdateCoordinator[TVState]):
    """Poll the TV for state; the library owns the serial link and reconnect."""

    config_entry: SonyTVRS232ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SonyTVRS232ConfigEntry,
        tv: SonyTV,
    ) -> None:
        """Initialize the coordinator around an unconnected TV."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            # TVState is a dataclass and every update hands over a copy, so
            # an unchanged poll does not wake the entities.
            always_update=False,
        )
        self.tv = tv
        self._tv_unsub: Callable[[], None] | None = None
        self._power_on_unsub: Callable[[], None] | None = None
        self._polling = False

    @override
    async def _async_setup(self) -> None:
        """Open the serial port, then subscribe to the library's notifications.

        ``connect()`` runs the handshake: arm standby listening, probe query
        support with a power query, and query the rest when the TV is on.
        """
        try:
            await self.tv.connect()
        except (SerialKitError, OSError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        self._tv_unsub = self.tv.subscribe(self._handle_state)
        self._sync_interval()

    @override
    async def _async_update_data(self) -> TVState:
        """Poll the TV: power first, and the rest only when it is on."""
        tv = self.tv
        if not tv.connected:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="not_connected",
            )
        if self.data is None or tv.supports_queries is False:
            # First refresh: the handshake just populated state. Set-only TV:
            # a query would only burn a timeout.
            return tv.state.copy()
        self._polling = True
        try:
            try:
                power = await tv.query_power()
            except SerialKitError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                    translation_placeholders={"error": str(err)},
                ) from err
            if power is PowerState.ON:
                for query in (tv.query_input_source, tv.query_volume, tv.query_mute):
                    try:
                        await query()
                    except CommandTimeoutError, ProtocolError:
                        # This model does not answer that one; keep the last value.
                        continue
        finally:
            self._polling = False
        return tv.state.copy()

    @callback
    def _sync_interval(self) -> None:
        """Stop the poll timer for a TV that does not answer queries."""
        self.update_interval = (
            None if self.tv.supports_queries is False else SCAN_INTERVAL
        )

    @callback
    def _handle_state(self, state: TVState | None) -> None:
        """Reflect a library notification into the coordinator.

        ``None`` means the serial link dropped; the library reconnects on its
        own, so only the outage is surfaced here.
        """
        if state is None:
            self._cancel_power_on_refresh()
            self.async_set_update_error(
                ConnectionLostError("Serial connection to the TV lost")
            )
            return
        if self._polling:
            # The poll returns the snapshot itself; a mid-poll push would be a
            # partial state.
            return
        previous = self.data.power if self.data is not None else None
        if (
            previous is PowerState.OFF
            and state.power is PowerState.ON
            and self.tv.supports_queries
        ):
            self._schedule_power_on_refresh()
        self.async_set_updated_data(state.copy())

    @callback
    @override
    def async_set_updated_data(self, data: TVState) -> None:
        """Accept a pushed state; log the recovery the base class only logs on a poll."""
        if not self.last_update_success:
            LOGGER.info("Connection to %s restored", self.name)
        self._sync_interval()
        super().async_set_updated_data(data)

    @callback
    def _schedule_power_on_refresh(self) -> None:
        """Re-query the TV once it has had time to boot (cancel-before-re-arm)."""
        self._cancel_power_on_refresh()
        self._power_on_unsub = async_call_later(
            self.hass, POWER_ON_REFRESH_DELAY, self._async_power_on_refresh
        )

    @callback
    def _cancel_power_on_refresh(self) -> None:
        if self._power_on_unsub is not None:
            self._power_on_unsub()
            self._power_on_unsub = None

    async def _async_power_on_refresh(self, _now: datetime) -> None:
        self._power_on_unsub = None
        await self.async_request_refresh()

    @override
    async def async_shutdown(self) -> None:
        """Stop polling and close the serial connection."""
        self._cancel_power_on_refresh()
        if self._tv_unsub is not None:
            self._tv_unsub()
            self._tv_unsub = None
        await self.tv.disconnect()
        await super().async_shutdown()
