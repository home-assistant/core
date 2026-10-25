"""The OneDrive for Business integration."""

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING, cast

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)

from homeassistant.components.backup import async_get_manager
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
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


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
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


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
    """Unload a OneDrive config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
    """Migrate old entry."""
    if entry.version == 1 and entry.minor_version == 1:
        if TYPE_CHECKING:
            assert entry.unique_id
        # Microsoft returns drive IDs with inconsistent casing
        drive_id = entry.unique_id.upper()

        entity_registry = er.async_get(hass)

        @callback
        def _uppercase_drive_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            if entity_entry.unique_id.startswith(drive_id):
                return None
            new_unique_id = drive_id + entity_entry.unique_id[len(drive_id) :]
            # A casing flip may already have created a duplicate with the new ID
            if (
                (
                    existing_entity_id := entity_registry.async_get_entity_id(
                        entity_entry.domain, DOMAIN, new_unique_id
                    )
                )
                and (existing_entity := entity_registry.async_get(existing_entity_id))
                and existing_entity.config_entry_id == entry.entry_id
            ):
                entity_registry.async_remove(entity_entry.entity_id)
                return None
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, _uppercase_drive_id)
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            uppercase_device = device_registry.async_get_device_by_identifier(
                (DOMAIN, drive_id), entry.entry_id
            )
            if uppercase_device is None:
                device_registry.async_update_device(
                    device.id, new_identifiers={(DOMAIN, drive_id)}
                )
            elif uppercase_device.id != device.id:
                # Duplicate created by a casing flip
                device_registry.async_remove_device(device.id)
        if entry.unique_id != drive_id:
            async_get_manager(hass).async_rename_agent(
                f"{DOMAIN}.{entry.unique_id}", f"{DOMAIN}.{drive_id}"
            )
        hass.config_entries.async_update_entry(
            entry, unique_id=drive_id, minor_version=2
        )
        _LOGGER.debug("Migration to version 1.2 successful")


async def _get_onedrive_client(
    hass: HomeAssistant, entry: OneDriveConfigEntry
) -> tuple[OneDriveClient, Callable[[], Awaitable[str]]]:
    """Get OneDrive client."""
    with tenant_id_context(entry.data[CONF_TENANT_ID]):
        implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    # Refresh up front, so a failure surfaces here instead of from inside the client
    await session.async_ensure_token_valid()

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
