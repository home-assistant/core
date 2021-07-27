"""DataUpdateCoordinator for the Yale integration."""
from __future__ import annotations

from datetime import timedelta

from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


class YaleDataUpdateCoordinator(DataUpdateCoordinator):
    """A Yale Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Yale hub."""
        self.entry = entry
        self.yale: YaleSmartAlarmClient | None = None
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

        for device in updates["cycle"]["device_status"]:
            state = device["status1"]
            if device["type"] == "device_type.door_lock":
                lock_status_str = device["minigw_lock_status"]
                lock_status = int(str(lock_status_str or 0), 16)
                closed = (lock_status & 16) == 16
                locked = (lock_status & 1) == 1
                if not lock_status and "device_status.lock" in state:
                    device["_state"] = "locked"
                    locks.append(device)
                    continue
                if not lock_status and "device_status.unlock" in state:
                    device["_state"] = "unlocked"
                    locks.append(device)
                    continue
                if (
                    lock_status
                    and (
                        "device_status.lock" in state or "device_status.unlock" in state
                    )
                    and closed
                    and locked
                ):
                    device["_state"] = "locked"
                    locks.append(device)
                    continue
                if (
                    lock_status
                    and (
                        "device_status.lock" in state or "device_status.unlock" in state
                    )
                    and closed
                    and not locked
                ):
                    device["_state"] = "unlocked"
                    locks.append(device)
                    continue
                if (
                    lock_status
                    and (
                        "device_status.lock" in state or "device_status.unlock" in state
                    )
                    and not closed
                ):
                    device["_state"] = "unlocked"
                    locks.append(device)
                    continue
                device["_state"] = "unavailable"
                locks.append(device)
                continue
            if device["type"] == "device_type.door_contact":
                if "device_status.dc_close" in state:
                    device["_state"] = "closed"
                    door_windows.append(device)
                    continue
                if "device_status.dc_open" in state:
                    device["_state"] = "open"
                    door_windows.append(device)
                    continue
                device["_state"] = "unavailable"
                door_windows.append(device)
                continue

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
            arm_status = self.yale.get_armed_status()
            cycle = self.yale.get_cycle()
            status = self.yale.get_status()
            online = self.yale.get_online()

        except AuthenticationError as error:
            LOGGER.error("Authentication failed. Check credentials %s", error)
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_REAUTH, "entry_id": self.entry.entry_id},
                    data=self.entry.data,
                )
            )
            raise UpdateFailed from error

        return {
            "arm_status": arm_status,
            "cycle": cycle,
            "status": status,
            "online": online,
        }
