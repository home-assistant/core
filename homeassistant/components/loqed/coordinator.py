"""Provides the coordinator for a LOQED lock."""
import logging

from aiohttp.web import Request
import async_timeout
from loqedAPI import loqed

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LoqedDataCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the loqed platform."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: loqed.LoqedAPI,
        lock: loqed.Lock,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Loqed Data Update coordinator."""
        super().__init__(hass, _LOGGER, name="Loqed sensors")
        self._hass = hass
        self._api = api
        self._entry = entry
        self.lock = lock

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from API endpoint."""
        async with async_timeout.timeout(10):
            return await self._api.async_get_lock_details()

    @callback
    async def _handle_webhook(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> None:
        """Handle incoming Loqed messages."""
        _LOGGER.debug("Callback received: %s", request.headers)
        received_ts = request.headers["TIMESTAMP"]
        received_hash = request.headers["HASH"]
        body = await request.text()

        _LOGGER.debug("Callback body: %s", body)

        event_data = await self.lock.receiveWebhook(body, received_hash, received_ts)
        if "error" in event_data:
            _LOGGER.warning("Incorrect callback received:: %s", event_data)
            return

        self.async_set_updated_data(event_data)

    async def ensure_webhooks(self) -> None:
        """Register webhook on LOQED bridge."""
        webhook_id = self._entry.data[CONF_WEBHOOK_ID]

        webhook.async_register(
            self.hass, DOMAIN, "Loqed", webhook_id, self._handle_webhook
        )
        webhook_url = webhook.async_generate_url(self.hass, webhook_id)
        _LOGGER.info("Webhook URL: %s", webhook_url)

        webhooks = await self.lock.getWebhooks()

        webhook_index = next(
            (x["id"] for x in webhooks if x["url"] == webhook_url), None
        )

        if not webhook_index:
            await self.lock.registerWebhook(webhook_url)
            webhooks = await self.lock.getWebhooks()
            webhook_index = next(x["id"] for x in webhooks if x["url"] == webhook_url)

            _LOGGER.info("Webhook got index %s", webhook_index)

    async def remove_webhooks(self) -> None:
        """Remove webhook from LOQED bridge."""
        webhook_id = self._entry.data[CONF_WEBHOOK_ID]
        webhook_url = webhook.async_generate_url(self.hass, webhook_id)

        webhook.async_unregister(
            self.hass,
            webhook_id,
        )
        _LOGGER.info("Webhook URL: %s", webhook_url)

        webhooks = await self.lock.getWebhooks()

        webhook_index = next(
            (x["id"] for x in webhooks if x["url"] == webhook_url), None
        )

        if webhook_index:
            await self.lock.deleteWebhook(webhook_index)
