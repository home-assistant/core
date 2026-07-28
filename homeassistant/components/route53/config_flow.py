"""Config flow for AWS Route53 integration."""

import logging
from typing import Any, override

import boto3
import botocore.exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_ZONE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_DOMAIN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_RECORDS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiple=True)
        ),
        vol.Optional(CONF_TTL, default=DEFAULT_TTL): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=86400,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        ),
    }
)


def _validate_auth(
    aws_access_key_id: str, aws_secret_access_key: str, zone: str
) -> None:
    """Validate we can access Route53."""
    client = boto3.client(
        "route53",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    # Check if we can get the hosted zone to verify auth and zone
    client.get_hosted_zone(Id=zone)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    await hass.async_add_executor_job(
        _validate_auth,
        data[CONF_ACCESS_KEY_ID],
        data[CONF_SECRET_ACCESS_KEY],
        data[CONF_ZONE],
    )


class Route53ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Route53."""

    VERSION = 1

    async def _async_validate(self, user_input: dict[str, Any]) -> str | None:
        """Validate the input, returning an error key when it fails."""
        try:
            await validate_input(self.hass, user_input)
        except botocore.exceptions.ClientError as err:
            _LOGGER.error("Failed to connect to AWS: %s", err)
            return "invalid_auth"
        except botocore.exceptions.BotoCoreError as err:
            _LOGGER.error("BotoCore error: %s", err)
            return "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_ZONE: user_input[CONF_ZONE],
                    CONF_DOMAIN: user_input[CONF_DOMAIN],
                }
            )

            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_DOMAIN], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_ZONE: user_input[CONF_ZONE],
                    CONF_DOMAIN: user_input[CONF_DOMAIN],
                }
            )

            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=user_input[CONF_DOMAIN],
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # Check if already configured
        self._async_abort_entries_match(
            {
                CONF_ZONE: user_input[CONF_ZONE],
                CONF_DOMAIN: user_input[CONF_DOMAIN],
            }
        )

        if error := await self._async_validate(user_input):
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=user_input[CONF_DOMAIN],
            data=user_input,
        )
