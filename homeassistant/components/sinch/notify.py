"""Support for Sinch notifications."""

from __future__ import annotations

import logging

from clx.xms.api import MtBatchTextSmsResult
from clx.xms.client import Client
from clx.xms.exceptions import (
    ErrorResponseException,
    NotFoundException,
    UnauthorizedException,
    UnexpectedResponseException,
)
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SENDER
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEFAULT_RECIPIENTS, CONF_SERVICE_PLAN_ID, DEFAULT_SENDER, DOMAIN

ATTR_SENDER = CONF_SENDER

_LOGGER = logging.getLogger(__name__)


# Deprecated in Home Assistant 2024.4
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SERVICE_PLAN_ID): cv.string,
        vol.Optional(CONF_SENDER, default=DEFAULT_SENDER): cv.string,
        vol.Optional(CONF_DEFAULT_RECIPIENTS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sinch notify entity platform."""
    async_add_entities(
        [
            SinchNotifiyEntity(
                unique_id=config_entry.data.get(CONF_SERVICE_PLAN_ID),
                device_name="Sinch",
                config_entry=config_entry,
            )
        ]
    )


class SinchNotifiyEntity(NotifyEntity):
    """Representation of a Sinch notify entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        entity_name: str | None,
        config_entry: ConfigEntry | None,
    ) -> None:
        """Initialize the Sinch notify entity."""
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_name = entity_name
        self.default_recipients = config_entry.options.get(CONF_DEFAULT_RECIPIENTS, [])
        self.sender = config_entry.options.get(CONF_SENDER, DEFAULT_SENDER)
        self.client = Client(
            config_entry.data.get(CONF_SERVICE_PLAN_ID),
            config_entry.data.get(CONF_API_KEY),
        )

    def send_message(self, message: str, **kwargs: any) -> None:
        """Send a message to a user."""
        targets = kwargs.get(ATTR_TARGET, self.default_recipients)
        data = kwargs.get(ATTR_DATA) or {}

        clx_args = {ATTR_MESSAGE: message, ATTR_SENDER: self.sender}

        if ATTR_SENDER in data:
            clx_args[ATTR_SENDER] = data[ATTR_SENDER]

        if not targets:
            _LOGGER.error("At least 1 target is required")
            return None

        try:
            for target in targets:
                result: MtBatchTextSmsResult = self.client.create_text_message(
                    clx_args[ATTR_SENDER], target, clx_args[ATTR_MESSAGE]
                )
                batch_id = result.batch_id
                _LOGGER.debug(
                    'Successfully sent SMS to "%s" (batch_id: %s)', target, batch_id
                )
        except ErrorResponseException as ex:
            _LOGGER.error(
                "Caught ErrorResponseException. Response code: %s (%s)",
                ex.error_code,
                ex,
            )
        except NotFoundException as ex:
            _LOGGER.error("Caught NotFoundException (request URL: %s)", ex.url)
        except UnauthorizedException as ex:
            _LOGGER.error(
                "Caught UnauthorizedException (service plan: %s)", ex.service_plan_id
            )
        except UnexpectedResponseException as ex:
            _LOGGER.error("Caught UnexpectedResponseException: %s", ex)
