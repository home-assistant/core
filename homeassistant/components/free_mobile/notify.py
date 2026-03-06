"""Support for Free Mobile SMS platform."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from freesms import FreeClient
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORMS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> FreeSMSNotificationService | None:
    """Get the Free Mobile SMS notification service."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") == "already_configured"
    ):
        # Config entry already exists - create issue and return None to prevent
        # duplicate notification services (entity via config entry + legacy via YAML)
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2026.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            translation_key="deprecated_yaml",
            severity=ir.IssueSeverity.WARNING,
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Free Mobile",
            },
        )
        return None

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Free Mobile",
            },
        )
        await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
        return FreeSMSNotificationService(
            config[CONF_USERNAME], config[CONF_ACCESS_TOKEN]
        )

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        translation_key="deprecated_yaml",
        severity=ir.IssueSeverity.WARNING,
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Free Mobile",
        },
    )

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    return FreeSMSNotificationService(config[CONF_USERNAME], config[CONF_ACCESS_TOKEN])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Free Mobile SMS notification service."""
    async_add_entities([FreeSMSNotifyEntity(config_entry)])


class FreeSMSNotifyEntity(NotifyEntity):
    """Implement a notification service for the Free Mobile SMS service."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the service."""
        self._config_entry = config_entry
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Free Mobile",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the Free Mobile user cell."""
        # Get the client from runtime_data
        client: FreeClient = self._config_entry.runtime_data
        await self.hass.async_add_executor_job(self._send_sms, message, client)

    def _send_sms(self, message: str, client: FreeClient) -> None:
        """Send SMS via Free Mobile API (blocking call)."""
        resp = client.send_sms(message)

        if resp.status_code == HTTPStatus.BAD_REQUEST:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == HTTPStatus.FORBIDDEN:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            _LOGGER.error("Server error, try later")
        elif resp.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.error("Too many SMS sent in a short time")


class FreeSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the Free Mobile SMS service."""

    def __init__(self, username: str, access_token: str) -> None:
        """Initialize the service."""
        self._free_client = FreeClient(username, access_token)

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the Free Mobile user cell."""
        resp = self._free_client.send_sms(message)

        if resp.status_code == HTTPStatus.BAD_REQUEST:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == HTTPStatus.FORBIDDEN:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            _LOGGER.error("Server error, try later")
        elif resp.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.error("Too many SMS sent in a short time")
