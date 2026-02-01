"""The Ghost integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from aioghost import GhostAdminAPI
from aioghost.exceptions import GhostAuthError, GhostError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DEFAULT_TITLE,
    DOMAIN,
    WEBHOOK_EVENTS,
)
from .coordinator import GhostDataUpdateCoordinator
from .webhook import async_register_webhook, async_unregister_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GhostConfigEntry = ConfigEntry[GhostRuntimeData]


@dataclass
class GhostRuntimeData:
    """Runtime data for Ghost integration."""

    coordinator: GhostDataUpdateCoordinator
    api: GhostAdminAPI
    ghost_webhook_ids: list[str] = field(default_factory=list)
    webhooks_enabled: bool = False


def _get_external_url(hass: HomeAssistant) -> str | None:
    """Try to get an external URL for webhooks."""
    try:
        url: str = get_url(hass, allow_internal=False, prefer_cloud=True)
        if url and url.startswith("https://"):
            return url
    except NoURLAvailableError:
        pass
    return None


async def async_setup_entry(hass: HomeAssistant, entry: GhostConfigEntry) -> bool:
    """Set up Ghost from a config entry."""
    api_url = entry.data[CONF_API_URL]
    admin_api_key = entry.data[CONF_ADMIN_API_KEY]

    api = GhostAdminAPI(api_url, admin_api_key, session=async_get_clientsession(hass))

    try:
        site = await api.get_site()
        site_title = site.get("title", DEFAULT_TITLE)
    except GhostAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_api_key",
        ) from err
    except GhostError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinator = GhostDataUpdateCoordinator(hass, api, site_title)
    await coordinator.async_config_entry_first_refresh()

    runtime_data = GhostRuntimeData(coordinator=coordinator, api=api)

    external_url = _get_external_url(hass)
    if external_url:
        webhook_ids = await _setup_webhooks(hass, entry, api, site_title, external_url)
        runtime_data.ghost_webhook_ids = webhook_ids
        runtime_data.webhooks_enabled = True
        _LOGGER.info("Ghost webhooks enabled for %s", site_title)
    else:
        _LOGGER.debug("No external URL available, webhooks disabled for %s", site_title)

    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _setup_webhooks(
    hass: HomeAssistant,
    entry: ConfigEntry,
    api: GhostAdminAPI,
    site_title: str,
    webhook_url: str,
) -> list[str]:
    """Set up webhooks for real-time events. Returns list of Ghost webhook IDs."""
    ha_webhook_id = await async_register_webhook(hass, entry.entry_id, site_title)
    ha_webhook_url = f"{webhook_url}/api/webhook/{ha_webhook_id}"

    _LOGGER.info("Setting up Ghost webhooks to %s", ha_webhook_url)

    ghost_webhook_ids = []
    for event in WEBHOOK_EVENTS:
        try:
            webhook = await api.create_webhook(event, ha_webhook_url)
            if ghost_wh_id := webhook.get("id"):
                ghost_webhook_ids.append(ghost_wh_id)
                _LOGGER.debug("Created Ghost webhook for %s: %s", event, ghost_wh_id)
        except GhostError as err:
            _LOGGER.warning("Failed to create webhook for %s: %s", event, err)

    _LOGGER.info("Created %d Ghost webhooks", len(ghost_webhook_ids))
    return ghost_webhook_ids


async def async_unload_entry(hass: HomeAssistant, entry: GhostConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime_data = entry.runtime_data

        for webhook_id in runtime_data.ghost_webhook_ids:
            try:
                await runtime_data.api.delete_webhook(webhook_id)
                _LOGGER.debug("Deleted Ghost webhook %s", webhook_id)
            except GhostError as err:
                _LOGGER.warning(
                    "Failed to delete Ghost webhook %s: %s", webhook_id, err
                )

        if runtime_data.webhooks_enabled:
            async_unregister_webhook(hass, entry.entry_id)

    return unload_ok
