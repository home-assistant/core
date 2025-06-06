"""Config flow for the Backblaze integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from b2sdk.v2 import B2Api, InMemoryAccountInfo, exception
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_APPLICATION_KEY, CONF_BUCKET, CONF_KEY_ID, CONF_PREFIX, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY_ID): cv.string,
        vol.Required(CONF_APPLICATION_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Optional(CONF_PREFIX, default=""): cv.string,
    }
)


class BackblazeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Backblaze."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_KEY_ID: user_input[CONF_KEY_ID],
                    CONF_APPLICATION_KEY: user_input[CONF_APPLICATION_KEY],
                }
            )

            info = InMemoryAccountInfo()
            b2_api = B2Api(info)

            try:

                def authorize_and_get_bucket() -> None:
                    """Authorize account and get bucket by name."""
                    b2_api.authorize_account(
                        "production",
                        user_input[CONF_KEY_ID],
                        user_input[CONF_APPLICATION_KEY],
                    )
                    b2_api.get_bucket_by_name(user_input[CONF_BUCKET])

                await self.hass.async_add_executor_job(authorize_and_get_bucket)

                allowed = b2_api.account_info.get_allowed()

                # Check if capabilities contains 'writeFiles' and 'listFiles' and 'deleteFiles' and 'readFiles'
                if allowed is not None:
                    capabilities = allowed["capabilities"]
                    if not capabilities or not all(
                        capability in capabilities
                        for capability in (
                            "writeFiles",
                            "listFiles",
                            "deleteFiles",
                            "readFiles",
                        )
                    ):
                        errors["base"] = "invalid_capability"

                    prefix: str = user_input[CONF_PREFIX]
                    allowed_prefix = cast(str, allowed.get("namePrefix", ""))
                    if allowed_prefix and not prefix.startswith(allowed_prefix):
                        errors[CONF_PREFIX] = "invalid_prefix"
                        placeholders["allowed_prefix"] = allowed_prefix

                    if prefix and not prefix.endswith("/"):
                        user_input[CONF_PREFIX] = f"{prefix}/"

            except exception.Unauthorized:
                errors["base"] = "invalid_credentials"
            except exception.RestrictedBucket as err:
                placeholders["restricted_bucket_name"] = err.bucket_name
                errors[CONF_BUCKET] = "restricted_bucket"
            except exception.NonExistentBucket:
                errors[CONF_BUCKET] = "invalid_bucket_name"
            except exception.ConnectionReset:
                errors["base"] = "cannot_connect"
            except exception.MissingAccountData:
                errors["base"] = "invalid_credentials"
            else:
                if not errors:
                    return self.async_create_entry(
                        title=user_input[CONF_BUCKET], data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
