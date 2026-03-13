"""YoLink local hub message listener."""

from typing import Any

from yolink.device import YoLinkDevice
from yolink.message_listener import MessageListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class LocalHubMessageListener(MessageListener):
    """YoLink Local hub home message listener."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init message listener."""
        self._hass = hass
        self._entry = entry

    def on_message(self, device: YoLinkDevice, msg_data: dict[str, Any]) -> None:
        """On message received."""
        coordinators = (
            self._entry.runtime_data[1]
            if self._entry.runtime_data is not None
            else None
        )
        if not coordinators:
            return
        if (coordinator := coordinators.get(device.device_id)) is not None:
            coordinator.async_set_updated_data(msg_data)
