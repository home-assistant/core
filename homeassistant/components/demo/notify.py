"""Demo notification entity."""

from __future__ import annotations

from homeassistant.components.notify import DOMAIN, NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

EVENT_NOTIFY = "notify"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo entity platform."""
    async_add_entities([DemoNotifyEntity(unique_id="notify", device_name="Notifier")])


class DemoNotifyEntity(NotifyEntity):
    """Implement demo notification platform."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        unique_id: str,
        device_name: str,
    ) -> None:
        """Initialize the Demo button entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )

    async def async_send_message(self, message: str) -> None:
        """Send a message to a user."""
        event_notitifcation = {"message": message}
        self.hass.bus.async_fire(EVENT_NOTIFY, event_notitifcation)
