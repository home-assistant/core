"""The loqed integration."""
from __future__ import annotations

import logging

from aiohttp.web import Request
import async_timeout
from loqedAPI import loqed

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_COORDINATOR, CONF_LOCK, CONF_WEBHOOK_INDEX, DOMAIN

PLATFORMS: list[str] = [Platform.LOCK, Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


@callback
async def _handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None:
    """Handle incoming Loqed messages."""
    _LOGGER.debug("Callback received: %s", str(request.headers))
    received_ts = request.headers["TIMESTAMP"]
    received_hash = request.headers["HASH"]
    body = await request.text()

    _LOGGER.debug("Callback body: %s", body)

    entry = next(
        entry
        for entry in hass.data[DOMAIN].values()
        if entry[CONF_WEBHOOK_ID] == webhook_id
    )
    lock: loqed.Lock = entry[CONF_LOCK]
    coordinator: LoqedDataCoordinator = entry[CONF_COORDINATOR]

    event_data = await lock.receiveWebhook(body, received_hash, received_ts)
    if "error" in event_data:
        _LOGGER.warning("Incorrect callback received:: %s", event_data)
        return

    coordinator.async_set_updated_data(event_data)


async def _ensure_webhooks(
    hass: HomeAssistant, webhook_id: str, lock: loqed.Lock
) -> int:
    webhook.async_register(hass, DOMAIN, "Loqed", webhook_id, _handle_webhook)
    webhook_url = webhook.async_generate_url(hass, webhook_id)
    _LOGGER.info("Webhook URL: %s", webhook_url)

    webhooks = await lock.getWebhooks()

    webhook_index = next((x["id"] for x in webhooks if x["url"] == webhook_url), None)

    if not webhook_index:
        await lock.registerWebhook(webhook_url)
        webhooks = await lock.getWebhooks()
        webhook_index = next(x["id"] for x in webhooks if x["url"] == webhook_url)

        _LOGGER.info("Webhook got index %s", webhook_index)

    return int(webhook_index)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up loqed from a config entry."""
    websession = async_get_clientsession(hass)
    host = entry.data["host"]
    apiclient = loqed.APIClient(websession, f"http://{host}")
    api = loqed.LoqedAPI(apiclient)

    lock = await api.async_get_lock(
        entry.data["api_key"],
        entry.data["bkey"],
        entry.data["key_id"],
        entry.data["host"],
    )
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    webhook_index = await _ensure_webhooks(hass, webhook_id, lock)
    coordinator = LoqedDataCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONF_WEBHOOK_ID: webhook_id,
        CONF_LOCK: lock,
        CONF_COORDINATOR: coordinator,
        CONF_WEBHOOK_INDEX: webhook_index,
    }

    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    webhook.async_unregister(hass, data[CONF_WEBHOOK_ID])
    lock: loqed.Lock = data[CONF_LOCK]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    try:
        await lock.deleteWebhook(data[CONF_WEBHOOK_INDEX])
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to delete webhook")
        return False

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class LoqedDataCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the loqed platform."""

    def __init__(self, hass: HomeAssistant, api: loqed.LoqedAPI) -> None:
        """Initialize the Loqed Data Update coordinator."""
        super().__init__(hass, _LOGGER, name="Loqed sensors")
        self._api = api

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from API endpoint."""
        async with async_timeout.timeout(10):
            return await self._api.async_get_lock_details()
