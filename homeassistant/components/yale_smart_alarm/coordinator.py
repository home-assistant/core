"""DataUpdateCoordinator for the Yale integration."""
from __future__ import annotations

from datetime import timedelta

from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class YaleDataUpdateCoordinator(DataUpdateCoordinator):
    """A Yale Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Verisure hub."""
        self._entry = entry
        self._hass = hass
        self._yale = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Yale."""

        if self._yale is None:
            self._yale = await self._hass.async_add_executor_job(
                YaleSmartAlarmClient,
                self._entry.data[CONF_USERNAME],
                self._entry.data[CONF_PASSWORD],
            )

        try:
            arm_status = await self._hass.async_add_executor_job(
                self._yale.get_armed_status  # type: ignore[attr-defined]
            )
            cycle = await self._hass.async_add_executor_job(
                self._yale.get_cycle  # type: ignore[attr-defined]
            )
            status = await self._hass.async_add_executor_job(
                self._yale.get_status  # type: ignore[attr-defined]
            )
            online = await self._hass.async_add_executor_job(
                self._yale.get_online  # type: ignore[attr-defined]
            )

        except AuthenticationError as ae:
            LOGGER.error("Authentication failed. Check credentials %s", ae)
            raise

        locks = []
        door_windows = []

        for lock in cycle["data"]["device_status"]:
            if lock["type"] == "device_type.door_lock":
                state = lock["status1"]
                lock_status_str = lock["minigw_lock_status"]
                if lock_status_str != "":
                    lock_status = int(lock_status_str, 16)
                    closed = (lock_status & 16) == 16
                    locked = (lock_status & 1) == 1
                    if closed is True and locked is True:
                        state = STATE_LOCKED
                    elif closed is True and locked is False:
                        state = STATE_UNLOCKED
                    elif not closed:
                        state = STATE_UNLOCKED
                elif "device_status.lock" in state:
                    state = STATE_LOCKED
                elif "device_status.unlock" in state:
                    state = STATE_UNLOCKED
                else:
                    state = STATE_UNAVAILABLE
                lock["_state"] = state
                locks.append(lock)

        for door_window in cycle["data"]["device_status"]:
            if door_window["type"] == "device_type.door_contact":
                state = door_window["status1"]
                if "device_status.dc_close" in state:
                    state = "closed"
                elif "device_status.dc_open" in state:
                    state = "open"
                else:
                    state = STATE_UNAVAILABLE
                door_window["_state"] = state
                door_windows.append(door_window)

        debug = {
            "alarm": arm_status,
            "locks": locks,
            "door_windows": door_windows,
            "status": status,
            "online": online,
        }
        LOGGER.debug(f"{debug}")
        return {
            "alarm": arm_status,
            "locks": locks,
            "door_windows": door_windows,
            "status": status,
            "online": online,
        }
