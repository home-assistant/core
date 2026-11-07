"""Keep a Fronius inverter's limits alive over Modbus."""

import asyncio
from datetime import datetime
import logging

from fronius_modbus import Controls, FroniusModbusInverter, Storage, SunSpecError
from modbus_connection import ModbusError

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import HEARTBEAT_INTERVAL, SolarNetId


def power_limit_active(controls: Controls | None) -> bool:
    """Return whether an AC power limit is in force."""
    return controls is not None and controls.enabled is True


def battery_limits_active(storage: Storage | None) -> bool:
    """Return whether a battery charge or discharge limit is in force."""
    return storage is not None and (
        storage.charge_limit_enabled is True or storage.discharge_limit_enabled is True
    )


class LimitHeartbeat:
    """Keep active limits alive against the device's fallback.

    The device holds the AC power limit and the battery limits only for as
    long as it keeps hearing them, so with a fallback period set they are
    sent again well before the period is up.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        modbus_inverter: FroniusModbusInverter,
        *,
        device_lock: asyncio.Lock,
        revert_seconds: int,
        logger: logging.Logger,
        solar_net_id: SolarNetId,
    ) -> None:
        """Set up the heartbeat of one inverter."""
        self._hass = hass
        self._modbus_inverter = modbus_inverter
        self._device_lock = device_lock
        self._revert_seconds = revert_seconds
        self._logger = logger
        self._solar_net_id = solar_net_id
        self._unsub: CALLBACK_TYPE | None = None
        self._stopped = False

    async def async_start(self) -> None:
        """Send active limits right away and keep them alive from then on.

        Right away because the device may have been counting down while Home
        Assistant was not running.
        """
        # the first refresh may have scheduled a beat already
        self._async_cancel()
        if self._revert_seconds:
            await self._async_beat()

    async def _async_beat(self, _now: datetime | None = None) -> None:
        """Send the limits again and line up the next beat."""
        self._unsub = None
        await self.async_resend_power_limit()
        await self.async_resend_battery_limits()
        self.async_update()

    @callback
    def async_update(self) -> None:
        """Beat only while there is a limit to keep alive."""
        if (
            self._stopped
            or not self._revert_seconds
            or not (
                power_limit_active(self._modbus_inverter.controls)
                or battery_limits_active(self._modbus_inverter.storage)
            )
        ):
            self._async_cancel()
            return
        if self._unsub is None:
            self._unsub = async_call_later(
                self._hass, HEARTBEAT_INTERVAL, self._async_beat
            )

    @callback
    def async_stop(self) -> None:
        """Stop beating for good, even from a beat that is under way."""
        self._stopped = True
        self._async_cancel()

    @callback
    def _async_cancel(self) -> None:
        """Drop a pending beat."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def async_resend_power_limit(self) -> None:
        """Send an active power limit again to restart the fallback period.

        Only a write restarts the period, so the limit is written again
        rather than just read. Nothing is sent while no limit is in force,
        decided on a fresh read, so a limit released on the device since the
        last poll is not taken back here.
        """
        controls = self._modbus_inverter.controls
        if controls is None:
            return
        try:
            async with self._device_lock:
                await controls.refresh_power_limit(revert_seconds=self._revert_seconds)
        except (ModbusError, SunSpecError) as err:
            self._logger.warning(
                "Could not send the AC power limit to inverter %s again: %s",
                self._solar_net_id,
                err,
            )

    async def async_resend_battery_limits(self) -> None:
        """Send active battery limits again to restart the fallback period.

        Like the power limit, decided on a fresh read and only while a limit
        is in force.
        """
        storage = self._modbus_inverter.storage
        if storage is None:
            return
        try:
            async with self._device_lock:
                await storage.refresh_limits(revert_seconds=self._revert_seconds)
        except (ModbusError, SunSpecError) as err:
            self._logger.warning(
                "Could not send the battery limits to inverter %s again: %s",
                self._solar_net_id,
                err,
            )
