"""DataUpdateCoordinator for the Yale integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from yalesmartalarmclient.client import YaleSmartAlarmClient
from yalesmartalarmclient.exceptions import AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, YALE_BASE_ERRORS


class YaleDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """A Yale Data Update Coordinator."""

    yale: YaleSmartAlarmClient

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Yale hub."""
        self.entry = entry
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )

    async def _async_setup(self) -> None:
        """Set up connection to Yale."""
        try:
            self.yale = YaleSmartAlarmClient(
                self.entry.data[CONF_USERNAME], self.entry.data[CONF_PASSWORD]
            )
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except YALE_BASE_ERRORS as error:
            raise UpdateFailed from error

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Yale."""

        updates = await self.hass.async_add_executor_job(self.get_updates)

        locks = []
        door_windows = []
        temp_sensors = []

        for device in updates["cycle"]["device_status"]:
            state = device["status1"]
            if device["type"] == "device_type.door_lock":
                lock_status_str = device["minigw_lock_status"]
                lock_status = int(str(lock_status_str or 0), 16)
                closed = (lock_status & 16) == 16
                locked = (lock_status & 1) == 1
                if not lock_status and "device_status.lock" in state:
                    device["_state"] = "locked"
                    device["_state2"] = "unknown"
                    locks.append(device)
                    continue
                if not lock_status and "device_status.unlock" in state:
                    device["_state"] = "unlocked"
                    device["_state2"] = "unknown"
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
                    device["_state2"] = "closed"
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
                    device["_state2"] = "closed"
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
                    device["_state2"] = "open"
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
            if device["type"] == "device_type.temperature_sensor":
                temp_sensors.append(device)

        _sensor_map = {
            contact["address"]: contact["_state"] for contact in door_windows
        }
        _lock_map = {lock["address"]: lock["_state"] for lock in locks}
        _temp_map = {temp["address"]: temp["status_temp"] for temp in temp_sensors}

        return {
            "alarm": updates["arm_status"],
            "locks": locks,
            "door_windows": door_windows,
            "temp_sensors": temp_sensors,
            "status": updates["status"],
            "online": updates["online"],
            "sensor_map": _sensor_map,
            "temp_map": _temp_map,
            "lock_map": _lock_map,
            "panel_info": updates["panel_info"],
        }

    def get_updates(self) -> dict[str, Any]:
        """Fetch data from Yale."""
        try:
            arm_status = self.yale.get_armed_status()
            data = self.yale.get_information()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except YALE_BASE_ERRORS as error:
            raise UpdateFailed from error

        return {
            "arm_status": arm_status,
            "cycle": data.cycle,
            "status": data.status,
            "online": data.online,
            "panel_info": data.panel_info,
        }
