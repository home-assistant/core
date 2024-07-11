"""A Bluetooth passive coordinator.

Receives data from advertisements but can also poll.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from bleak import BleakError
from bluetooth_data_tools import monotonic_time_coarse

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer

from . import BluetoothChange, BluetoothScanningMode, BluetoothServiceInfoBleak
from .passive_update_coordinator import PassiveBluetoothDataUpdateCoordinator

POLL_DEFAULT_COOLDOWN = 10
POLL_DEFAULT_IMMEDIATE = True


class ActiveBluetoothDataUpdateCoordinator[_T](PassiveBluetoothDataUpdateCoordinator):
    """A coordinator that receives passive data from advertisements but can also poll.

    Unlike the passive processor coordinator, this coordinator does call a parser
    method to parse the data from the advertisement.

    Every time an advertisement is received, needs_poll_method is called to work
    out if a poll is needed. This should return True if it is and False if it is
    not needed.

    def needs_poll_method(
        svc_info: BluetoothServiceInfoBleak,
        last_poll: float | None
    ) -> bool:
        return True

    If there has been no poll since HA started, `last_poll` will be None.
    Otherwise it is the number of seconds since one was last attempted.

    If a poll is needed, the coordinator will call poll_method. This is a coroutine.
    It should return the same type of data as your update_method. The expectation is
    that data from advertisements and from polling are being parsed and fed into
    a shared object that represents the current state of the device.

    async def poll_method(svc_info: BluetoothServiceInfoBleak) -> YourDataType:
        return YourDataType(....)

    BluetoothServiceInfoBleak.device contains a BLEDevice. You should use this in
    your poll function, as it is the most efficient way to get a BleakClient.

    Once the poll is complete, the coordinator will call _async_handle_bluetooth_poll
    which needs to be implemented in the subclass.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
        mode: BluetoothScanningMode,
        needs_poll_method: Callable[[BluetoothServiceInfoBleak, float | None], bool],
        poll_method: Callable[
            [BluetoothServiceInfoBleak],
            Coroutine[Any, Any, _T],
        ]
        | None = None,
        poll_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None,
        connectable: bool = True,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, logger, address, mode, connectable)
        # It's None before the first successful update.
        # Set type to just T to remove annoying checks that data is not None
        # when it was already checked during setup.
        self.data: _T = None  # type: ignore[assignment]

        self._needs_poll_method = needs_poll_method
        self._poll_method = poll_method
        self._last_poll: float | None = None
        self.last_poll_successful = True

        # We keep the last service info in case the poller needs to refer to
        # e.g. its BLEDevice
        self._last_service_info: BluetoothServiceInfoBleak | None = None

        if poll_debouncer is None:
            poll_debouncer = Debouncer(
                hass,
                logger,
                cooldown=POLL_DEFAULT_COOLDOWN,
                immediate=POLL_DEFAULT_IMMEDIATE,
                function=self._async_poll,
                background=True,
            )
        else:
            poll_debouncer.function = self._async_poll

        self._debounced_poll = poll_debouncer

    def needs_poll(self, service_info: BluetoothServiceInfoBleak) -> bool:
        """Return true if time to try and poll."""
        if self.hass.is_stopping:
            return False
        poll_age: float | None = None
        if self._last_poll:
            poll_age = service_info.time - self._last_poll
        return self._needs_poll_method(service_info, poll_age)

    async def _async_poll_data(
        self, last_service_info: BluetoothServiceInfoBleak
    ) -> _T:
        """Fetch the latest data from the source."""
        if self._poll_method is None:
            raise NotImplementedError("Poll method not implemented")
        return await self._poll_method(last_service_info)

    async def _async_poll(self) -> None:
        """Poll the device to retrieve any extra data."""
        assert self._last_service_info

        try:
            self.data = await self._async_poll_data(self._last_service_info)
        except BleakError as exc:
            if self.last_poll_successful:
                self.logger.error(
                    "%s: Bluetooth error whilst polling: %s", self.address, str(exc)
                )
                self.last_poll_successful = False
            return
        except Exception:  # noqa: BLE001
            if self.last_poll_successful:
                self.logger.exception("%s: Failure while polling", self.address)
                self.last_poll_successful = False
            return
        finally:
            self._last_poll = monotonic_time_coarse()

        if not self.last_poll_successful:
            self.logger.debug("%s: Polling recovered", self.address)
            self.last_poll_successful = True

        self._async_handle_bluetooth_poll()

    @callback
    def _async_handle_bluetooth_poll(self) -> None:
        """Handle a poll event."""
        self.async_update_listeners()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        super()._async_handle_bluetooth_event(service_info, change)

        self._last_service_info = service_info

        # See if its time to poll
        # We use bluetooth events to trigger the poll so that we scan as soon as
        # possible after a device comes online or back in range, if a poll is due
        if self.needs_poll(service_info):
            self._debounced_poll.async_schedule_call()

    @callback
    def _async_stop(self) -> None:
        """Cancel debouncer and stop the callbacks."""
        self._debounced_poll.async_cancel()
        super()._async_stop()
