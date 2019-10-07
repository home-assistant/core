"""StarLine Account."""
from datetime import timedelta, datetime
from starline import StarlineApi, StarlineDevice
from typing import List, Callable, Optional, Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, LOGGER, DEFAULT_SCAN_INTERVAL


class StarlineAccount:
    """StarLine Account class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Constructor."""
        self._hass: HomeAssistant = hass
        self._config_entry: ConfigEntry = config_entry
        self._update_listeners: List[Callable] = []
        self._update_interval: int = DEFAULT_SCAN_INTERVAL
        self._unsubscribe_auto_updater: Optional[Callable] = None
        self._api: StarlineApi = StarlineApi(
            config_entry.data["user_id"], config_entry.data["slnet_token"]
        )

    @property
    def api(self) -> StarlineApi:
        return self._api

    def set_update_interval(self, hass: HomeAssistant, interval: int) -> None:
        """Set StarLine API update interval."""
        LOGGER.debug("Setting update interval: %ds", interval)
        self._update_interval = interval
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()

        delta = timedelta(seconds=interval)
        self._unsubscribe_auto_updater = async_track_time_interval(
            hass, self._api.update, delta
        )

    def unload(self):
        """Unload StarLine API."""
        LOGGER.debug("Unloading StarLine API.")
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def device_info(self, device: StarlineDevice) -> Dict[str, Any]:
        """Device information for entities."""
        return {
            "identifiers": {(DOMAIN, device.device_id)},
            "manufacturer": "StarLine",
            "name": device.name,
            "sw_version": device.fw_version,
            "model": device.typename,
        }

    def gps_attrs(self, device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for device tracker."""
        return {
            "updated": datetime.utcfromtimestamp(device.position["ts"]).isoformat(),
            "online": device.online,
        }

    def balance_attrs(self, device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for balance sensor."""
        return {
            "operator": device.balance["operator"],
            "state": device.balance["state"],
            "updated": device.balance["ts"],
        }

    def gsm_attrs(self, device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for GSM sensor."""
        return {
            "raw": device.gsm_level,
            "imei": device.imei,
            "phone": device.phone,
            "online": device.online,
        }

    def engine_attrs(self, device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for engine switch."""
        return {
            "autostart": device.car_state["r_start"],
            "ignition": device.car_state["run"],
        }
