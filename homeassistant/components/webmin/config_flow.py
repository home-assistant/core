"""Config flow for Webmin."""
from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast
from xmlrpc.client import Fault

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
import voluptuous as vol
from webmin_xmlrpc.client import WebminInstance
from yarl import URL

from homeassistant.const import (
    CONF_HOST,
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
) -> dict[str, Any]:
    """Validate user input."""
    # pylint: disable-next=protected-access
    handler.parent_handler._async_abort_entries_match(
        {CONF_HOST: user_input[CONF_HOST]}
    )
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
        data = await instance.update()
        ifaces = [iface for iface in data["active_interfaces"] if "ether" in iface]
        ifaces.sort(key=lambda x: x["ether"])
        mac_address = ifaces[0]["ether"]
        await cast(SchemaConfigFlowHandler, handler.parent_handler).async_set_unique_id(
            mac_address
        )
        return user_input
    except ClientResponseError as err:
        if err.status == HTTPStatus.UNAUTHORIZED:
            raise SchemaFlowError("invalid_auth") from err
        raise SchemaFlowError("cannot_connect") from err
    except Fault as fault:
        raise SchemaFlowError(
            f"Fault {fault.faultCode}: {fault.faultString}"
        ) from fault
    except ClientConnectionError as err:
        raise SchemaFlowError("cannot_connect") from err
    except Exception as err:
        raise SchemaFlowError("unknown") from err


CONFIG_SCHEMA = vol.Schema(
    {
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
    """Handle a config flow for Webmin."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return str(options[CONF_HOST])
