"""Config flow for the Backblaze integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

from b2sdk.v2 import B2Api, InMemoryAccountInfo, exception
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    BACKBLAZE_REALM,
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    CONF_PREFIX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Constants
REQUIRED_CAPABILITIES = {"writeFiles", "listFiles", "deleteFiles", "readFiles"}

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

    reauth_entry: ConfigEntry[Any] | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            # Abort if an entry with the exact same Key ID and Application Key already exists
            self._async_abort_entries_match(
                {
                    CONF_KEY_ID: user_input[CONF_KEY_ID],
                    CONF_APPLICATION_KEY: user_input[CONF_APPLICATION_KEY],
                }
            )

            # Validate the provided Backblaze credentials and bucket
            errors, placeholders = await self._async_validate_backblaze_connection(
                user_input
            )

            if not errors:
                # Ensure the prefix always ends with a slash if it's not empty
                if user_input[CONF_PREFIX] and not user_input[CONF_PREFIX].endswith(
                    "/"
                ):
                    user_input[CONF_PREFIX] += "/"

                # Create the configuration entry
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET], data=user_input
                )

        # Show the configuration form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_validate_backblaze_connection(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Validate Backblaze credentials, bucket, capabilities, and prefix.

        Returns a tuple of (errors_dict, placeholders_dict).
        """
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        info = InMemoryAccountInfo()
        b2_api = B2Api(info)

        def _authorize_and_get_bucket_sync() -> None:
            """Synchronously authorize the account and get the bucket by name.

            This function is run in the executor because b2sdk operations are blocking.
            """
            b2_api.authorize_account(
                BACKBLAZE_REALM,  # Use the defined realm constant
                user_input[CONF_KEY_ID],
                user_input[CONF_APPLICATION_KEY],
            )
            b2_api.get_bucket_by_name(user_input[CONF_BUCKET])

        try:
            # Execute the blocking API calls in the event loop's executor
            await self.hass.async_add_executor_job(_authorize_and_get_bucket_sync)

            # Retrieve allowed capabilities after successful authorization
            allowed = b2_api.account_info.get_allowed()

            # Check for required capabilities
            if (
                allowed is None
                or not allowed.get("capabilities")
                or not REQUIRED_CAPABILITIES.issubset(set(allowed["capabilities"]))
            ):
                missing_caps = REQUIRED_CAPABILITIES - set(
                    allowed.get("capabilities", [])
                )
                if missing_caps:
                    _LOGGER.warning(
                        "Missing required Backblaze capabilities for Key ID '%s': %s",
                        user_input[CONF_KEY_ID],
                        ", ".join(sorted(missing_caps)),
                    )
                    errors["base"] = "invalid_capability"
                    # Provide specific missing capabilities for the frontend to display
                    placeholders["missing_capabilities"] = ", ".join(
                        sorted(missing_caps)
                    )

            # Validate the specified prefix against the allowed prefix (if any)
            configured_prefix: str = user_input[CONF_PREFIX]
            # cast to str as get() could return None, but namePrefix is expected to be str
            allowed_prefix = cast(str, allowed.get("namePrefix", ""))

            # If an allowed prefix is defined by Backblaze, ensure the configured prefix starts with it
            if allowed_prefix and not configured_prefix.startswith(allowed_prefix):
                errors[CONF_PREFIX] = "invalid_prefix"
                placeholders["allowed_prefix"] = allowed_prefix

        except exception.Unauthorized:
            _LOGGER.debug(
                "Backblaze authentication failed for Key ID '%s'",
                user_input[CONF_KEY_ID],
            )
            errors["base"] = "invalid_credentials"
        except exception.RestrictedBucket as err:
            _LOGGER.debug(
                "Access to Backblaze bucket '%s' is restricted: %s",
                user_input[CONF_BUCKET],
                err,
            )
            placeholders["restricted_bucket_name"] = err.bucket_name
            errors[CONF_BUCKET] = "restricted_bucket"
        except exception.NonExistentBucket:
            _LOGGER.debug(
                "Backblaze bucket '%s' does not exist", user_input[CONF_BUCKET]
            )
            errors[CONF_BUCKET] = "invalid_bucket_name"
        except exception.ConnectionReset:
            _LOGGER.error("Failed to connect to Backblaze. Connection reset")
            errors["base"] = "cannot_connect"
        except exception.MissingAccountData:
            # This generally indicates an issue with how InMemoryAccountInfo is used
            _LOGGER.error(
                "Missing account data during Backblaze authorization for Key ID '%s'",
                user_input[CONF_KEY_ID],
            )
            errors["base"] = "invalid_credentials"
        except Exception:
            _LOGGER.exception(
                "An unexpected error occurred during Backblaze configuration for Key ID '%s'",
                user_input[CONF_KEY_ID],
            )
            errors["base"] = "unknown"

        return errors, placeholders

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication flow."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert self.reauth_entry is not None
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        assert self.reauth_entry is not None
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            # Validate the new credentials
            validation_input = {
                CONF_KEY_ID: user_input[CONF_KEY_ID],
                CONF_APPLICATION_KEY: user_input[CONF_APPLICATION_KEY],
                CONF_BUCKET: self.reauth_entry.data[CONF_BUCKET],
                CONF_PREFIX: self.reauth_entry.data[CONF_PREFIX],
            }

            errors, placeholders = await self._async_validate_backblaze_connection(
                validation_input
            )

            if not errors:
                # Update the config entry with new credentials
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data_updates={
                        CONF_KEY_ID: user_input[CONF_KEY_ID],
                        CONF_APPLICATION_KEY: user_input[CONF_APPLICATION_KEY],
                    },
                )

        # Show the reauthentication form
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KEY_ID): cv.string,
                    vol.Required(CONF_APPLICATION_KEY): TextSelector(
                        config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "bucket": self.reauth_entry.data[CONF_BUCKET],
                **placeholders,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is not None:
            # Validate the reconfigured settings
            errors, placeholders = await self._async_validate_backblaze_connection(
                user_input
            )

            if not errors:
                # Ensure the prefix always ends with a slash if it's not empty
                if user_input[CONF_PREFIX] and not user_input[CONF_PREFIX].endswith(
                    "/"
                ):
                    user_input[CONF_PREFIX] += "/"

                # Update the configuration entry
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )
        else:
            errors = {}
            placeholders = {}

        # Show the reconfiguration form with current values
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
