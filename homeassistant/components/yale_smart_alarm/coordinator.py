"""DataUpdateCoordinator for the Yale integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from yalesmartalarmclient import YaleLock
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
        self.locks: list[YaleLock] = []

    async def _async_setup(self) -> None:
        """Set up connection to Yale."""
        try:
            self.yale = await self.hass.async_add_executor_job(
                YaleSmartAlarmClient,
                self.entry.data[CONF_USERNAME],
                self.entry.data[CONF_PASSWORD],
            )
            self.locks = await self.hass.async_add_executor_job(self.yale.get_locks)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except YALE_BASE_ERRORS as error:
            raise UpdateFailed from error

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Yale."""

        updates = await self.hass.async_add_executor_job(self.get_updates)

        door_windows = []
        temp_sensors = []

        for device in updates["cycle"]["device_status"]:
            state = device["status1"]
            if device["type"] == "device_type.door_contact":
                device["_battery"] = False
                if "device_status.low_battery" in state:
                    device["_battery"] = True
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
        _sensor_battery_map = {
            f"{contact["address"]}-battery": contact["_battery"]
            for contact in door_windows
        }
        _temp_map = {temp["address"]: temp["status_temp"] for temp in temp_sensors}

        return {
            "alarm": updates["arm_status"],
            "door_windows": door_windows,
            "temp_sensors": temp_sensors,
            "status": updates["status"],
            "online": updates["online"],
            "sensor_map": _sensor_map,
            "sensor_battery_map": _sensor_battery_map,
            "temp_map": _temp_map,
            "panel_info": updates["panel_info"],
        }

    def get_updates(self) -> dict[str, Any]:
        """Fetch data from Yale."""
        try:
            arm_status = self.yale.get_armed_status()
            data = self.yale.get_information()
            if TYPE_CHECKING:
                assert data.cycle
            for device in data.cycle["data"]["device_status"]:
                if device["type"] == YaleLock.DEVICE_TYPE:
                    for lock in self.locks:
                        if lock.name == device["name"]:
                            lock.update(device)
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed from error
        except YALE_BASE_ERRORS as error:
            raise UpdateFailed from error

        cycle = data.cycle["data"] if data.cycle else None
        status = data.status["data"] if data.status else None
        online = data.online["data"] if data.online else None
        panel_info = data.panel_info["data"] if data.panel_info else None

        return {
            "arm_status": arm_status,
            "cycle": cycle,
            "status": status,
            "online": online,
            "panel_info": panel_info,
        }
