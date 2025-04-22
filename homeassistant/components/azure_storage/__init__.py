"""The Azure Storage integration."""

from aiohttp import ClientTimeout
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.core.pipeline.transport._aiohttp import (
    AioHttpTransport,
)  # need to import from private file, as it is not properly imported in the init
from azure.storage.blob.aio import ContainerClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession

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
    # set increase aiohttp timeout for long running operations (up/download)
    session = async_create_clientsession(
        hass, timeout=ClientTimeout(connect=10, total=12 * 60 * 60)
    )
    container_client = ContainerClient(
        account_url=f"https://{entry.data[CONF_ACCOUNT_NAME]}.blob.core.windows.net/",
        container_name=entry.data[CONF_CONTAINER_NAME],
        credential=entry.data[CONF_STORAGE_ACCOUNT_KEY],
        transport=AioHttpTransport(session=session),
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
        raise ConfigEntryAuthFailed(
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

    def _async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureStorageConfigEntry
) -> bool:
    """Unload an Azure Storage config entry."""
    return True
