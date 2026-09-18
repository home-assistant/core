"""The Monzo integration."""

import contextlib
import logging

from aiohttp import ClientError
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError

from homeassistant.components import cloud
from homeassistant.components.webhook import async_generate_id
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .api import AuthenticatedMonzoAPI, MonzoAPI
from .const import CONF_CLOUDHOOK_URL, CONF_WEBHOOK_URL, DOMAIN
from .coordinator import MonzoConfigEntry, MonzoCoordinator, MonzoRuntimeData
from .helpers import get_authenticated_owner_name
from .services import async_setup_services
from .webhook import MonzoWebhookManager, async_delete_remote_webhooks

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]


async def _async_create_api(
    hass: HomeAssistant, entry: MonzoConfigEntry
) -> AuthenticatedMonzoAPI:
    """Create an authenticated Monzo API client."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    return AuthenticatedMonzoAPI(async_get_clientsession(hass), session)


async def _async_create_removal_api(
    hass: HomeAssistant, entry: MonzoConfigEntry
) -> MonzoAPI:
    """Create a Monzo API client without updating a deleted config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    token = session.token
    if not session.valid_token:
        token = await implementation.async_refresh_token(token)
    return MonzoAPI(async_get_clientsession(hass), token[CONF_ACCESS_TOKEN])


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Monzo integration."""
    async_setup_services(hass)
    return True


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

        # 1.2 -> 1.3: Add a stable webhook ID
        if minor_version < 3:
            data[CONF_WEBHOOK_ID] = async_generate_id()
            minor_version = 3

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
    external_api = await _async_create_api(hass, entry)

    coordinator = MonzoCoordinator(hass, entry, external_api)

    await coordinator.async_config_entry_first_refresh()
    if entry.title == DOMAIN and (
        owner_name := get_authenticated_owner_name(
            coordinator.data.accounts.values(), entry.unique_id
        )
    ):
        hass.config_entries.async_update_entry(entry, title=owner_name)

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
    """Remove webhooks for a deleted config entry."""
    if webhook_url := entry.data.get(CONF_WEBHOOK_URL):
        try:
            api = await _async_create_removal_api(hass, entry)
            accounts = await api.user_account.accounts()
            await async_delete_remote_webhooks(
                api, (account["id"] for account in accounts), webhook_url
            )
        except (
            AuthorisationExpiredError,
            ClientError,
            ImplementationUnavailableError,
            InvalidMonzoAPIResponseError,
            OAuth2TokenRequestError,
            TimeoutError,
        ) as err:
            _LOGGER.warning("Unable to remove Monzo webhooks: %s", err)

    if CONF_CLOUDHOOK_URL in entry.data:
        with contextlib.suppress(cloud.CloudNotAvailable):
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
