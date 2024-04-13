"""Clickatell platform for notify component."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.issue_registry as ir
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "clickatell"

BASE_API_URL = "https://platform.clickatell.com/messages/http/send"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Required(CONF_RECIPIENT): cv.string}
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up clickatell notify entity."""
    api_key = entry.data[CONF_API_KEY]
    recipient = entry.data[CONF_RECIPIENT]
    name = entry.title
    async_add_entities([ClickatellNotifyEntity(name, api_key, recipient)])


class ClickatellNotifyEntity(NotifyEntity):
    """Clickatell notify entity."""

    def __init__(self, name: str, api_key: str, recipient: str) -> None:
        """Initialize notify clickatell notify entity."""
        super().__init__()
        self._attr_name = name
        self._api_key = api_key
        self._recipient = recipient

    def send_message(self, message: str) -> None:
        """Send a message to a user."""
        data = {"apiKey": self._api_key, "to": self._recipient, "content": message}

        resp = requests.get(BASE_API_URL, params=data, timeout=5)
        if resp.status_code not in (HTTPStatus.OK, HTTPStatus.ACCEPTED):
            _LOGGER.error("Error %s : %s", resp.status_code, resp.text)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ClickatellNotificationService:
    """Get the Clickatell notification service."""
    recipient: str = config[CONF_RECIPIENT]
    name: str = config.get(CONF_NAME, recipient)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migration_notify_service_{recipient}",
        breaks_in_ha_version="2024.11.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        learn_more_url="https://www.home-assistant.io/integrations/clickatell",
        severity=ir.IssueSeverity.WARNING,
        translation_key="migration_notify_service",
        translation_placeholders={
            "domain": DOMAIN,
            "name": name,
            "integration_title": "Clickatell",
        },
    )
    return ClickatellNotificationService(config)


class ClickatellNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Clickatell service."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the service."""
        self.api_key: str = config[CONF_API_KEY]
        self.recipient: str = config[CONF_RECIPIENT]

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        data = {"apiKey": self.api_key, "to": self.recipient, "content": message}

        resp = requests.get(BASE_API_URL, params=data, timeout=5)
        if resp.status_code not in (HTTPStatus.OK, HTTPStatus.ACCEPTED):
            _LOGGER.error("Error %s : %s", resp.status_code, resp.text)
