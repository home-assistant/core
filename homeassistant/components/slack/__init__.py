"""The slack integration."""
from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientError
from slack import WebClient
from slack.errors import SlackApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv, discovery
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_URL,
    ATTR_USER_ID,
    DATA_CLIENT,
    DATA_HASS_CONFIG,
    DEFAULT_NAME,
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
    slack = WebClient(token=entry.data[CONF_API_KEY], run_async=True, session=session)

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


class SlackEntity(Entity):
    """Representation of a Slack entity."""

    _attr_attribution = "Data provided by Slack"
    _attr_has_entity_name = True

    def __init__(
        self,
        data: dict[str, str | WebClient],
        description: EntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Slack entity."""
        self._client = data[DATA_CLIENT]
        self.entity_description = description
        self._attr_unique_id = f"{data[ATTR_USER_ID]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=data[ATTR_URL],
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=entry.title,
        )
