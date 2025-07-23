"""Makes requests to the state server and stores the resulting data so that the buttons can access it."""

from dataclasses import dataclass
import functools
import logging
from typing import TYPE_CHECKING, TypedDict

from homelink.model.device import Device
from homelink.mqtt_provider import MQTTProvider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.ssl import get_default_context

if TYPE_CHECKING:
    from .event import HomeLinkEventEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class HomeLinkData:
    """Class for HomeLink integration runtime data."""

    provider: MQTTProvider
    coordinator: "HomeLinkCoordinator"
    last_update_id: str | None


class HomeLinkEventData(TypedDict):
    """Data for a single event."""

    request_id: str
    timestamp: int


class HomeLinkMQTTMessage(TypedDict):
    """HomeLink MQTT Event message."""

    type: str
    data: dict | HomeLinkEventData


class HomeLinkCoordinator(DataUpdateCoordinator[dict | HomeLinkEventData]):
    """HomeLink integration coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: MQTTProvider,
        config_entry: ConfigEntry[HomeLinkData],
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="HomeLink Coordinator",
            config_entry=config_entry,
        )
        self.provider = provider
        self.last_sync_timestamp = None
        self.last_sync_id = None
        self.device_data: list[Device] = []
        self.buttons: list[HomeLinkEventEntity] = []

    async def async_on_unload(self, _event):
        """Disconnect and unregister when unloaded."""
        await self.provider.disable()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        await self.provider.enable(get_default_context())

        await self.discover_devices()
        callback = functools.partial(on_message, self)
        self.provider.listen(callback)

    async def discover_devices(self):
        """Discover devices and build the Entities."""
        self.device_data = await self.provider.discover()

    async def _async_update_data(self) -> dict | HomeLinkEventData:
        """Fetch data from API endpoint. We only use manual updates so just return an empty dict."""
        return {}

    async def async_update_devices(self, message):
        """Update the devices from the server."""
        config_data = self.config_entry.data.copy()
        config_data["last_update_id"] = message["requestId"]
        await self.discover_devices()

        self.hass.config_entries.async_update_entry(self.config_entry, data=config_data)
        self.last_sync_id = message["requestId"]
        self.last_sync_timestamp = message["timestamp"]


def on_message(
    coordinator: HomeLinkCoordinator, _topic: str, message: HomeLinkMQTTMessage
):
    "MQTT Callback function."

    if message["type"] == "state":
        coordinator.hass.add_job(coordinator.async_set_updated_data, message["data"])
    if message["type"] == "requestSync":
        if coordinator.config_entry:
            coordinator.hass.add_job(
                coordinator.hass.config_entries.async_reload,
                coordinator.config_entry.entry_id,
            )
