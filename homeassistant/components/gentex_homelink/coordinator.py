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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import BaseDataUpdateCoordinatorProtocol
from homeassistant.util.ssl import get_default_context

if TYPE_CHECKING:
    from .event import HomeLinkEventEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HomeLinkData:
    """Class for HomeLink integration runtime data."""

    provider: MQTTProvider
    coordinator: HomeLinkCoordinator
    last_update_id: str | None


class HomeLinkEventData(TypedDict):
    """Data for a single event."""

    request_id: str
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
        config_entry: ConfigEntry[HomeLinkData],
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
        self._listeners: dict[int, tuple[CALLBACK_TYPE, object | None]] = {}
        self._last_listener_id: int = 0
        self.data: dict[str, HomeLinkEventData] | None = None
        self.last_update_success: bool = True

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for updates."""
        self._last_listener_id += 1
        self._listeners[self._last_listener_id] = (update_callback, context)
        return partial(self.__async_remove_listener_internal, self._last_listener_id)

    def __async_remove_listener_internal(self, listener_id: int):
        self._listeners.pop(listener_id)

    @callback
    def async_set_updated_data(self, data: dict[str, HomeLinkEventData]):
        """Manually update data and notify listeners."""
        self.data = data
        self.last_update_success = True
        self.async_update_listeners()

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()

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
