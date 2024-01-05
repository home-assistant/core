"""Config flow for Enigma2."""

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
from openwebif.api import OpenWebIfDevice
from openwebif.error import InvalidAuthError
import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers import selector
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=80): vol.All(
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
        vol.Required(CONF_SSL, default=False): selector.BooleanSelector(),
    }
)

IMPORT_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Optional(CONF_PORT, default=80): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
            )
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

    try:
        device = OpenWebIfDevice(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
            is_https=user_input[CONF_SSL],
        )
        await device.get_about()
        await device.close()
        return user_input
    except InvalidAuthError as error:
        raise SchemaFlowError("invalid_auth") from error
    except ClientError as error:
        raise SchemaFlowError("cannot_connect") from error
    except Exception as error:
        raise SchemaFlowError("unknown") from error


async def validate_import(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate import."""
    if CONF_PORT not in user_input:
        user_input[CONF_PORT] = DEFAULT_PORT
    if CONF_SSL not in user_input:
        user_input[CONF_SSL] = DEFAULT_SSL

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
