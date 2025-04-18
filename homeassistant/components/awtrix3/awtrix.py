"""Core components of AWTRIX Light."""

import logging

from homeassistant.core import HomeAssistant

from .common import async_get_coordinator_by_device_id, getIcon
from .const import CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


class AwtrixService:
    """Allows to send updated to applications."""

    def __init__(self,
                 hass: HomeAssistant
                 ) -> None:
        """Initialize the device."""

        self.hass = hass

    def api(self, data):
        """Create API on the fly."""
        result = []
        for device_id in data.get(CONF_DEVICE_ID):
            coordinator = async_get_coordinator_by_device_id(self.hass, device_id)
            result.append(coordinator.api)
        return result

    async def call(self, func, seq):
        """Call action API."""
        for i in seq:
            try:
                await func(i)
            except Exception:  # noqa: BLE001
                _LOGGER.error("Failed to call %s: action", i)

        return True

    async def push_app_data(self, data):
        """Update the application data."""

        app_id = data["name"]
        url = "custom?name=" + app_id

        action_data = data.get("data", {}) or {}
        payload = action_data.copy()
        payload.pop(CONF_DEVICE_ID, None)

        if 'icon' in payload:
            if str(payload["icon"]).startswith(('http://', 'https://')):
                payload["icon"] = await self.hass.async_add_executor_job(getIcon, str(payload["icon"]))

        return await self.call(lambda x: x.device_set_item_value(url, payload), self.api(data))

    async def switch_app(self, data):
        """Call API switch app."""

        url = "switch"
        app_id = data["name"]

        payload = {"name": app_id}
        return await self.call(lambda x: x.device_set_item_value(url, payload), self.api(data))

    async def settings(self, data):
        """Call API settings."""

        url = "settings"

        data = data or {}
        payload = data.copy()
        payload.pop(CONF_DEVICE_ID, None)

        return await self.call(lambda x: x.device_set_item_value(url, payload), self.api(data))

    async def rtttl(self, data):
        """Play rtttl."""

        url = "rtttl"
        payload = data["rtttl"]
        return await self.call(lambda x: x.device_set_item_value(url, payload), self.api(data))

    async def sound(self, data):
        """Play rtttl sound."""

        url = "sound"
        sound_id = data["sound"]
        payload = {"sound": sound_id}
        return await self.call(lambda x: x.device_set_item_value(url, payload), self.api(data))
