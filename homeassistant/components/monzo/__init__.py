"""The Monzo integration."""

import contextlib
import logging

from homeassistant.components import cloud
from homeassistant.components.webhook import async_generate_id
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AuthenticatedMonzoAPI
from .const import CONF_CLOUDHOOK_URL, DOMAIN
from .coordinator import MonzoConfigEntry, MonzoCoordinator, MonzoRuntimeData
from .webhook import MonzoWebhookManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]


async def async_migrate_entry(hass: HomeAssistant, entry: MonzoConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        data = dict(entry.data)
        minor_version = entry.minor_version
        unique_id = entry.unique_id

        # 1 -> 1.2: Unique ID from integer to string
        if minor_version == 1:
            unique_id = str(unique_id)
            minor_version = 2

        # 1.2/1.3 -> 1.4: Add a stable webhook ID
        if minor_version < 4:
            data[CONF_WEBHOOK_ID] = async_generate_id()
            minor_version = 4

        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=unique_id,
            minor_version=minor_version,
        )

    _LOGGER.debug("Migration successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: MonzoConfigEntry) -> bool:
    """Set up Monzo from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    external_api = AuthenticatedMonzoAPI(async_get_clientsession(hass), session)

    coordinator = MonzoCoordinator(hass, entry, external_api)

    await coordinator.async_config_entry_first_refresh()

    webhook_manager = MonzoWebhookManager(hass, entry, coordinator)
    entry.runtime_data = MonzoRuntimeData(coordinator, webhook_manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await webhook_manager.async_setup()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonzoConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.webhook_manager.async_unload()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: MonzoConfigEntry) -> None:
    """Remove the cloudhook for a deleted config entry."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        return
    with contextlib.suppress(cloud.CloudNotAvailable):
        await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
