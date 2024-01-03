"""Config flow for Webmin."""
from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
import voluptuous as vol
from webmin_xmlrpc.client import WebminInstance
from yarl import URL

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import DEFAULT_PORT, DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN


async def validate_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
):
    """Validate user input."""
    base_url = URL.build(
        scheme="https" if user_input[CONF_SSL] else "http",
        user=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
        host=user_input[CONF_HOST],
        port=int(user_input[CONF_PORT]),
    )
    session = async_create_clientsession(
        handler.parent_handler.hass,
        verify_ssl=user_input[CONF_VERIFY_SSL],
        base_url=base_url,
    )
    instance = WebminInstance(session=session)
    try:
        await instance.update()
        return user_input
    except ClientResponseError as e:
        if e.status == HTTPStatus.UNAUTHORIZED:
            raise SchemaFlowError("invalid_auth") from e
        raise SchemaFlowError("cannot_connect") from e
    except ClientConnectionError as e:
        raise SchemaFlowError("cannot_connect") from e
    except Exception as e:
        raise SchemaFlowError("unknown") from e


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): selector.BooleanSelector(),
        vol.Required(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=CONFIG_SCHEMA, validate_user_input=validate_user_input
    ),
}


class WebminConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for System Monitor."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        if CONF_NAME in options and options[CONF_NAME] is not None:
            return str(options[CONF_NAME])
        return str(options[CONF_HOST])
