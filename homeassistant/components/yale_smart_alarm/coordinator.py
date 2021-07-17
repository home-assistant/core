"""DataUpdateCoordinator for the Yale integration."""
from __future__ import annotations

from datetime import timedelta

from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class YaleDataUpdateCoordinator(DataUpdateCoordinator):
    """A Yale Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Yale hub."""
        self.entry = entry
        self.yale = None

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Yale."""

        updates = await self.hass.async_add_executor_job(self.get_updates)

        locks = []
        door_windows = []

        locks_list = (
            lock
            for lock in updates["cycle"]["data"]["device_status"]
            if lock["type"] == "device_type.door_lock"
        )

        for lock in locks_list:
            state = lock["status1"]
            lock_status_str = lock["minigw_lock_status"]
            if lock_status_str != "":
                lock_status = int(lock_status_str, 16)
                closed = (lock_status & 16) == 16
                locked = (lock_status & 1) == 1
                if closed is True and locked is True:
                    state = "locked"
                elif closed is True and locked is False:
                    state = "unlocked"
                elif not closed:
                    state = "unlocked"
            elif "device_status.lock" in state:
                state = "locked"
            elif "device_status.unlock" in state:
                state = "unlocked"
            else:
                state = "unavailable"
            lock["_state"] = state
            locks.append(lock)
        LOGGER.debug("locks: %s", locks)

        dorr_window_list = (
            door_window
            for door_window in updates["cycle"]["data"]["device_status"]
            if door_window["type"] == "device_type.door_contact"
        )

        for door_window in dorr_window_list:
            state = door_window["status1"]
            if "device_status.dc_close" in state:
                state = "closed"
            elif "device_status.dc_open" in state:
                state = "open"
            else:
                state = "unavailable"
            door_window["_state"] = state
            door_windows.append(door_window)

        return {
            "alarm": updates["arm_status"],
            "locks": locks,
            "door_windows": door_windows,
            "status": updates["status"],
            "online": updates["online"],
        }

    def get_updates(self) -> dict:
        """Fetch data from Yale."""

        if self.yale is None:
            self.yale = YaleSmartAlarmClient(
                self.entry.data[CONF_USERNAME], self.entry.data[CONF_PASSWORD]
            )

        try:
            arm_status = self.yale.get_armed_status()  # type: ignore[attr-defined]
            cycle = self.yale.get_cycle()  # type: ignore[attr-defined]
            status = self.yale.get_status()  # type: ignore[attr-defined]
            online = self.yale.get_online()  # type: ignore[attr-defined]

        except AuthenticationError as error:
            LOGGER.error("Authentication failed. Check credentials %s", error)
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_REAUTH},
                    data=self.entry.data,
                )
            )

        return {
            "arm_status": arm_status,
            "cycle": cycle,
            "status": status,
            "online": online,
        }
