"""Config flow for Enigma2."""

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
from openwebif.api import OpenWebIfDevice
from openwebif.error import InvalidAuthError
import voluptuous as vol
from yarl import URL

from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
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
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_DEEP_STANDBY,
    CONF_MAC_ADDRESS,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): selector.BooleanSelector(),
        vol.Required(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
    }
)

IMPORT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_SSL, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_DEEP_STANDBY): selector.BooleanSelector(),
        vol.Optional(CONF_SOURCE_BOUQUET): selector.TextSelector(),
        vol.Optional(CONF_USE_CHANNEL_ICON): selector.BooleanSelector(),
        vol.Optional(CONF_MAC_ADDRESS): selector.TextSelector(),
    }
)


async def validate_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input."""

    # pylint: disable-next=protected-access
    handler.parent_handler._async_abort_entries_match(
        {CONF_HOST: user_input[CONF_HOST]}
    )

    base_url = URL.build(
        scheme="http" if not user_input[CONF_SSL] else "https",
        host=user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        user=user_input.get(CONF_USERNAME),
        password=user_input.get(CONF_PASSWORD),
    )

    session = async_create_clientsession(
        handler.parent_handler.hass,
        verify_ssl=user_input[CONF_VERIFY_SSL],
        base_url=base_url,
    )

    try:
        about = await OpenWebIfDevice(session).get_about()
    except InvalidAuthError as error:
        raise SchemaFlowError("invalid_auth") from error
    except ClientError as error:
        raise SchemaFlowError("cannot_connect") from error
    except Exception as error:
        raise SchemaFlowError("unknown") from error

    if isinstance(handler.parent_handler, SchemaConfigFlowHandler):
        await handler.parent_handler.async_set_unique_id(
            about["info"]["ifaces"][0]["mac"]
        )
        # pylint: disable-next=protected-access
        handler.parent_handler._abort_if_unique_id_configured()
    return user_input


async def validate_import(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate import."""
    if CONF_PORT not in user_input:
        user_input[CONF_PORT] = DEFAULT_PORT
    if CONF_SSL not in user_input:
        user_input[CONF_SSL] = DEFAULT_SSL
    user_input[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL

    async_create_issue(
        handler.parent_handler.hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Enigma2",
        },
    )
    return await validate_user_input(handler, user_input)


class Enigma2ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Enigma2."""

    config_flow = {
        SOURCE_USER: SchemaFlowFormStep(
            schema=CONFIG_SCHEMA, validate_user_input=validate_user_input
        ),
        SOURCE_IMPORT: SchemaFlowFormStep(
            schema=IMPORT_CONFIG_SCHEMA, validate_user_input=validate_import
        ),
    }

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return str(options[CONF_HOST])
