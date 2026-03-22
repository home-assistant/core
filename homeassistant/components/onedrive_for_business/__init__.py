"""The OneDrive for Business integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import cast

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .application_credentials import tenant_id_context
from .const import (
    CONF_FOLDER_ID,
    CONF_FOLDER_PATH,
    CONF_TENANT_ID,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)
from .coordinator import (
    OneDriveConfigEntry,
    OneDriveForBusinessUpdateCoordinator,
    OneDriveRuntimeData,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    client, get_access_token = await _get_onedrive_client(hass, entry)

    folder_path = entry.data[CONF_FOLDER_PATH]

    try:
        backup_folder = await _handle_item_operation(
            lambda: client.get_drive_item(path_or_id=entry.data[CONF_FOLDER_ID]),
            folder_path,
        )
    except NotFoundError:
        _LOGGER.info("Creating backup folder %s", folder_path)
        backup_folder = await _handle_item_operation(
            lambda: client.create_folder(parent_id="root", name=folder_path),
            folder_path,
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_FOLDER_ID: backup_folder.id}
        )

    coordinator = OneDriveForBusinessUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OneDriveRuntimeData(
        client=client,
        token_function=get_access_token,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _get_onedrive_client(
    hass: HomeAssistant, entry: OneDriveConfigEntry
) -> tuple[OneDriveClient, Callable[[], Awaitable[str]]]:
    """Get OneDrive client."""
    with tenant_id_context(entry.data[CONF_TENANT_ID]):
        try:
            implementation = await async_get_config_entry_implementation(hass, entry)
        except ImplementationUnavailableError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="oauth2_implementation_unavailable",
            ) from err
    session = OAuth2Session(hass, entry, implementation)

    async def get_access_token() -> str:
        await session.async_ensure_token_valid()
        return cast(str, session.token[CONF_ACCESS_TOKEN])

    return (
        OneDriveClient(get_access_token, async_get_clientsession(hass)),
        get_access_token,
    )


async def _handle_item_operation[T](func: Callable[[], Awaitable[T]], folder: str) -> T:
    try:
        return await func()
    except NotFoundError:
        raise
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except (OneDriveException, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": folder},
        ) from err
