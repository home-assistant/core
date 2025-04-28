"""Event."""

from aiohttp.hdrs import METH_GET, METH_POST
from aiohttp.web import Request, Response

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EkeyBionyxConfigEntry
from .const import DOMAIN, LOGGER


class EkeyEvent(EventEntity):
    """Ekey Event."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["webhook_fired"]

    def __init__(
        self,
        data: dict[str, str],
    ) -> None:
        """Initialise a Ekey event entity."""
        self._attr_name = data["name"]
        self._attr_unique_id = data["ekey_id"]
        self._webhook_id = data["webhook_id"]

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle the webhook event."""
        self._trigger_event(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""

        async def async_webhook_handler(
            hass: HomeAssistant, webhook_id: str, request: Request
        ) -> Response | None:
            self._async_handle_event("webhook_fired")
            return None

        webhook_register(
            self.hass,
            DOMAIN,
            f"Ekey {self._attr_name}",
            self._webhook_id,
            async_webhook_handler,
            allowed_methods=[METH_GET, METH_POST],
        )
        LOGGER.info(
            webhook_generate_url(
                self.hass, self._webhook_id, allow_external=False, allow_ip=True
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister Webhook."""
        webhook_unregister(self.hass, self._webhook_id)
        LOGGER.info("Unregistered Webhook")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EkeyBionyxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Ekey event."""
    LOGGER.info(entry.data)
    async_add_entities(EkeyEvent(data) for data in entry.data["webhooks"])
