"""The slack integration."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_URL,
    ATTR_USER_ID,
    DATA_CLIENT,
    DATA_HASS_CONFIG,
    DOMAIN,
    SLACK_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Slack component."""
    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Slack from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    slack = AsyncWebClient(
        token=entry.data[CONF_API_KEY], session=session
    )  # No run_async

    try:
        res = await slack.auth_test()
    except (SlackApiError, ClientError) as ex:
        if isinstance(ex, SlackApiError) and ex.response["error"] == "invalid_auth":
            _LOGGER.error("Invalid API key")
            return False
        raise ConfigEntryNotReady("Error while setting up integration") from ex

    data = {
        DATA_CLIENT: slack,
        ATTR_URL: res[ATTR_URL],
        ATTR_USER_ID: res[ATTR_USER_ID],
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data | {SLACK_DATA: data}

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DATA_HASS_CONFIG],
        )
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True
