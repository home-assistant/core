"""The TRMNL integration."""

from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientError
from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError, TRMNLNotFoundError

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import config_validation as cv, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CLIENT_ID,
    CONF_HOME_ENTITIES,
    CONF_HOME_PLUGIN_SETTING_ID,
    DOMAIN,
    HOMEY_PLUGIN_ID,
    LOGGER,
)
from .coordinator import TRMNLConfigEntry, TRMNLCoordinator, scope_granted
from .home import HomePusher

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.TIME]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TRMNL OAuth client."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, "", name="TRMNL")
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Set up TRMNL from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    coordinator = TRMNLCoordinator(
        hass, entry, OAuth2Session(hass, entry, implementation)
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if entity_ids := entry.options.get(CONF_HOME_ENTITIES):
        entry.async_on_unload(
            HomePusher(hass, entry, entity_ids, _home_push(hass, entry)).async_start()
        )


def _home_push(
    hass: HomeAssistant, entry: TRMNLConfigEntry
) -> Callable[[dict[str, Any]], Coroutine[Any, Any, None]]:
    """Return a push to the entry's Homey plugin setting, made again if the user deleted it."""
    coordinator = entry.runtime_data

    async def create_plugin_setting() -> int:
        plugin_setting = await coordinator.client.create_plugin_setting(
            hass.config.location_name, HOMEY_PLUGIN_ID
        )
        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_HOME_PLUGIN_SETTING_ID: plugin_setting.identifier,
            },
        )
        return plugin_setting.identifier

    async def push(snapshot: dict[str, Any]) -> None:
        await coordinator.async_ensure_token_valid()
        plugin_setting_id = entry.options.get(CONF_HOME_PLUGIN_SETTING_ID)
        if plugin_setting_id is None:
            plugin_setting_id = await create_plugin_setting()
        try:
            await coordinator.client.update_plugin_setting_data(
                plugin_setting_id, snapshot
            )
        except TRMNLNotFoundError:
            await coordinator.client.update_plugin_setting_data(
                await create_plugin_setting(), snapshot
            )

    return push


async def async_unload_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Trade the account API key of a version 1 entry for an OAuth token."""
    # Core also calls this for a newer minor version, which is already OAuth.
    if entry.version != 1:
        return
    client = TRMNLClient(
        token=entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )
    # TRMNL keeps one connection per name, and many installs share the location name "Home".
    name = f"{hass.config.location_name} ({(await instance_id.async_get(hass))[:8]})"
    try:
        token = await client.migrate_to_oauth(CLIENT_ID, name)
    except TRMNLAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="migration_failed"
        ) from err
    except (TRMNLError, TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="migration_connection_error"
        ) from err

    # The user may have signed in to the same account with OAuth while this entry failed to load.
    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, token.sub):
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="migration_duplicate"
        )

    hass.config_entries.async_update_entry(
        entry,
        unique_id=token.sub,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "token_type": token.token_type,
                "expires_in": token.expires_in,
                "scope": token.scope,
                "expires_at": token.created_at + token.expires_in,
            },
        },
        version=2,
    )


async def async_remove_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> None:
    """Delete the plugin setting the integration created, if the user granted delete."""
    plugin_setting_id = entry.options.get(CONF_HOME_PLUGIN_SETTING_ID)
    if plugin_setting_id is None or not scope_granted(entry, "delete"):
        return
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
        await TRMNLClient(
            token=session.token["access_token"],
            session=async_get_clientsession(hass),
        ).delete_plugin_setting(plugin_setting_id)
    except (ClientError, TRMNLError) as err:
        LOGGER.warning("Could not delete the TRMNL home plugin setting: %s", err)
