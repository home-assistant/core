"""Config flow for the S3 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from ._api import (
    CannotConnectError,
    InvalidBucketNameError,
    InvalidCredentialsError,
    InvalidEndpointURLError,
    get_client,
)
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Required(
            CONF_ENDPOINT_URL, default="https://s3.eu-central-1.amazonaws.com/"
        ): TextSelector(config=TextSelectorConfig(type=TextSelectorType.URL)),
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    async with get_client(data):
        pass


class S3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_BUCKET])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(user_input)
            except InvalidCredentialsError:
                errors["base"] = "invalid_credentials"
            except InvalidBucketNameError:
                errors[CONF_BUCKET] = "invalid_bucket_name"
            except InvalidEndpointURLError:
                errors[CONF_ENDPOINT_URL] = "invalid_endpoint_url"
            except CannotConnectError:
                errors[CONF_ENDPOINT_URL] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
