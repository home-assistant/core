"""Establish MQTT connection and listen for event data."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TypedDict

from homelink.model.device import Device
from homelink.mqtt_provider import MQTTProvider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.ssl import get_default_context

type HomeLinkConfigEntry = ConfigEntry[HomeLinkCoordinator]
type EventCallback = Callable[[HomeLinkEventData], None]


class HomeLinkEventData(TypedDict):
    """Data for a single event."""

    requestId: str
    timestamp: int


class HomeLinkMQTTMessage(TypedDict):
    """HomeLink MQTT Event message."""

    type: str
    data: dict[str, HomeLinkEventData]  # Each key is a button id


class HomeLinkCoordinator:
    """HomeLink integration coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: MQTTProvider,
        config_entry: HomeLinkConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        self.hass = hass
        self.config_entry = config_entry
        self.provider = provider
        self.device_data: list[Device] = []
        self._listeners: dict[str, EventCallback] = {}

    @callback
    def async_add_event_listener(
        self, update_callback: EventCallback, target_event_id: str
    ) -> Callable[[], None]:
        """Listen for updates."""
        self._listeners[target_event_id] = update_callback
        return partial(self.__async_remove_listener_internal, target_event_id)

    def __async_remove_listener_internal(self, listener_id: str) -> None:
        del self._listeners[listener_id]

    @callback
    def async_handle_state_data(self, data: dict[str, HomeLinkEventData]) -> None:
        """Notify listeners."""
        for button_id, event in data.items():
            if listener := self._listeners.get(button_id):
                listener(event)

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup."""
        await self._async_setup()

    async def async_on_unload(self, _event) -> None:
        """Disconnect and unregister when unloaded."""
        await self.provider.disable()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        await self.provider.enable(get_default_context())
        await self.discover_devices()
        self.provider.listen(self.on_message)

    async def discover_devices(self) -> None:
        """Discover devices and build the Entities."""
        self.device_data = await self.provider.discover()

    def on_message(self, _topic: str, message: HomeLinkMQTTMessage) -> None:
        """MQTT Callback function."""
        if message["type"] == "state":
            self.hass.add_job(self.async_handle_state_data, message["data"])
        if message["type"] == "requestSync":
            self.hass.add_job(
                self.hass.config_entries.async_reload,
                self.config_entry.entry_id,
            )
