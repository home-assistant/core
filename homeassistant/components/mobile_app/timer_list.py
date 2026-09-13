"""Timer list for mobile app devices."""

from homeassistant.components.timer_list import InMemoryTimerListEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .util import supports_push

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the timer list for a push-capable mobile app device."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    if not supports_push(hass, webhook_id):
        # Finished timers are delivered as push notifications.
        return

    async_add_entities(
        [
            InMemoryTimerListEntity(
                name="Timers",
                unique_id=f"{webhook_id}-timer_list",
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, entry.data[ATTR_DEVICE_ID])}
                ),
            )
        ]
    )
