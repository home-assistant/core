"""The WebDAV integration."""

import logging

from aiowebdav2.exceptions import (
    ConnectionExceptionError,
    NoConnectionError,
    UnauthorizedError,
)

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BACKUP_PATH, DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .helpers import WebDavConfigEntry, async_create_client, async_ensure_path_exists
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WebDAV integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WebDavConfigEntry) -> None:
    """Set up WebDAV from a config entry."""
    client = async_create_client(
        hass=hass,
        url=entry.data[CONF_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, True),
    )

    path = entry.data.get(CONF_BACKUP_PATH, "/")

    try:
        path_exists = await async_ensure_path_exists(client, path)
    except UnauthorizedError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_username_password",
        ) from err
    except (ConnectionExceptionError, NoConnectionError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    if not path_exists:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_access_or_create_backup_path",
        )

    entry.runtime_data = client

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))


async def async_unload_entry(hass: HomeAssistant, entry: WebDavConfigEntry) -> None:
    """Unload a WebDAV config entry."""
