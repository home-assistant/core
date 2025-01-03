"""The Azure Storage integration."""

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.core.pipeline.transport import (  # pylint: disable=no-name-in-module
    AioHttpTransport,
)
from azure.storage.blob.aio import ContainerClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_CONTAINER_NAME,
    CONF_STORAGE_ACCOUNT_KEY,
    DATA_BACKUP_AGENT_LISTENERS,
    DOMAIN,
)

type AzureStorageConfigEntry = ConfigEntry[ContainerClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: AzureStorageConfigEntry
) -> bool:
    """Set up Azure Storage integration."""
    container_client = ContainerClient(
        account_url=f"https://{entry.data[CONF_ACCOUNT_NAME]}.blob.core.windows.net/",
        container_name=entry.data[CONF_CONTAINER_NAME],
        credential=entry.data[CONF_STORAGE_ACCOUNT_KEY],
        transport=AioHttpTransport(session=async_get_clientsession(hass)),
    )

    try:
        if not await container_client.exists():
            await container_client.create_container()
    except ResourceNotFoundError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="account_not_found",
            translation_placeholders={CONF_ACCOUNT_NAME: entry.data[CONF_ACCOUNT_NAME]},
        ) from err
    except ClientAuthenticationError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={CONF_ACCOUNT_NAME: entry.data[CONF_ACCOUNT_NAME]},
        ) from err
    except HttpResponseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={CONF_ACCOUNT_NAME: entry.data[CONF_ACCOUNT_NAME]},
        ) from err

    entry.runtime_data = container_client

    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureStorageConfigEntry
) -> bool:
    """Unload Azure Storage config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
