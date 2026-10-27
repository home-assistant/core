"""Keep a Fronius inverter's power limit alive over Modbus."""

import asyncio
from datetime import datetime
import logging

from fronius_modbus import FroniusModbusInverter, SunSpecError
from modbus_connection import ModbusError

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import HEARTBEAT_INTERVAL, SolarNetId


class PowerLimitHeartbeat:
    """Keep an active power limit alive against the device's fallback.

    The device holds a power limit only for as long as it keeps hearing it,
    so with a fallback period set the limit is sent again well before the
    period is up.
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
        """Send an active limit right away and keep it alive from then on.

        Right away because the device may have been counting down while Home
        Assistant was not running.
        """
        # the first refresh may have scheduled a beat already
        self.async_cancel()
        if self._revert_seconds:
            await self._async_beat()

    async def _async_beat(self, _now: datetime | None = None) -> None:
        """Send the limit again and line up the next beat."""
        self._unsub = None
        await self.async_resend_power_limit()
        self.async_update()

    @callback
    def async_update(self) -> None:
        """Beat only while there is a limit to keep alive."""
        controls = self._modbus_inverter.controls
        if (
            self._stopped
            or not self._revert_seconds
            or controls is None
            or not controls.enabled
        ):
            self.async_cancel()
            return
        if self._unsub is None:
            self._unsub = async_call_later(
                self._hass, HEARTBEAT_INTERVAL, self._async_beat
            )

    @callback
    def async_stop(self) -> None:
        """Stop beating for good, even from a beat that is under way."""
        self._stopped = True
        self.async_cancel()

    @callback
    def async_cancel(self) -> None:
        """Drop a pending beat."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def async_resend_power_limit(self) -> None:
        """Send an active power limit again to restart the fallback period.

        Fronius documents the period as restarted by every received Modbus
        message, but a Gen24 dropped the limit on time while being read every
        five seconds - only writing the limit again restarts it.

        Nothing to do while no limit is in force: without one there is no
        period running that could be restarted or cleared. That is decided on
        a fresh read, so a limit released on the device since the last poll
        is not taken back here.
        """
        controls = self._modbus_inverter.controls
        if controls is None:
            return
        try:
            async with self._device_lock:
                await controls.async_update()
                if not controls.enabled or (limit := controls.power_limit) is None:
                    return
                # the same registers `set_power_limit` writes - but that one
                # would enable the limit, and this may only refresh a running one
                await controls.write("revert_seconds", self._revert_seconds)
                await controls.write("power_limit", limit)
                await controls.write("enabled", True)
        except (ModbusError, SunSpecError) as err:
            self._logger.warning(
                "Could not send the AC power limit to inverter %s again: %s",
                self._solar_net_id,
                err,
            )
