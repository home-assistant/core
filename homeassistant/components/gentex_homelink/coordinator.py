"""Makes requests to the state server and stores the resulting data so that the buttons can access it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, TypedDict

from homelink.model.device import Device
from homelink.mqtt_provider import MQTTProvider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import BaseDataUpdateCoordinatorProtocol
from homeassistant.util.ssl import get_default_context

if TYPE_CHECKING:
    from .event import HomeLinkEventEntity

_LOGGER = logging.getLogger(__name__)

type HomeLinkConfigEntry = ConfigEntry[HomeLinkData]
type EventCallback = Callable[[HomeLinkEventData], None]


@dataclass
class HomeLinkData:
    """Class for HomeLink integration runtime data."""

    provider: MQTTProvider
    coordinator: HomeLinkCoordinator
    last_update_id: str | None


class HomeLinkEventData(TypedDict):
    """Data for a single event."""

    requestId: str
    timestamp: int


class HomeLinkMQTTMessage(TypedDict):
    """HomeLink MQTT Event message."""

    type: str
    data: dict[str, HomeLinkEventData]  # Each key is a button id


class HomeLinkCoordinator(BaseDataUpdateCoordinatorProtocol):
    """HomeLink integration coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: MQTTProvider,
        config_entry: HomeLinkConfigEntry,
    ) -> None:
        """Initialize my coordinator."""
        self.hass = hass
        self.logger = _LOGGER
        self.name = "HomeLinkCoordinator"
        self.config_entry = config_entry
        self.provider = provider
        self.last_sync_timestamp = None
        self.last_sync_id = None
        self.device_data: list[Device] = []
        self.buttons: list[HomeLinkEventEntity] = []
        self._listeners: dict[str, tuple[EventCallback, object | None]] = {}
        self.data: dict[str, HomeLinkEventData] | None = None
        self.last_update_success: bool = True

    @callback
    def async_add_event_listener(
        self, update_callback: EventCallback, context: Any = None
    ) -> Callable[[], None]:
        """Listen for updates."""
        self._listeners[context] = (update_callback, context)
        return partial(self.__async_remove_listener_internal, context)

    def __async_remove_listener_internal(self, listener_id: str):
        del self._listeners[listener_id]

    @callback
    def async_set_updated_data(self, data: dict[str, HomeLinkEventData]):
        """Manually update data and notify listeners."""
        self.data = data
        self.last_update_success = True
        self.async_update_listeners()

    @callback
    def async_update_listeners(self) -> None:
        """Update the listeners who have data relevant to listeners."""
        if not self.data:
            return
        for button_id in self.data:
            if button_id in self._listeners:
                self._listeners[button_id][0](self.data[button_id])

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup."""
        await self._async_setup()

    async def async_on_unload(self, _event):
        """Disconnect and unregister when unloaded."""
        await self.provider.disable()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        await self.provider.enable(get_default_context())
        await self.discover_devices()
        self.provider.listen(self.on_message)

    async def discover_devices(self):
        """Discover devices and build the Entities."""
        self.device_data = await self.provider.discover()

    def on_message(
        self: HomeLinkCoordinator, _topic: str, message: HomeLinkMQTTMessage
    ):
        "MQTT Callback function."
        if message["type"] == "state":
            self.hass.add_job(self.async_set_updated_data, message["data"])
        if message["type"] == "requestSync":
            if self.config_entry:
                self.hass.add_job(
                    self.hass.config_entries.async_reload,
                    self.config_entry.entry_id,
                )
