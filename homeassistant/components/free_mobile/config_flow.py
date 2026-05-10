"""Config flow for Free Mobile notification."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from freesms import FreeClient
import requests.exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FreeMobileConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Free Mobile config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate configuration before sending test SMS
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            client: FreeClient | None = None
            # Create a FreeClient to validate credentials
            # The freesms library uses assert statements that raise AssertionError
            # when credentials are missing or invalid. We catch this to provide
            # user-friendly error messages. Unexpected AssertionErrors are re-raised
            # to avoid masking programming errors.
            try:
                client = FreeClient(
                    user_input[CONF_USERNAME], user_input[CONF_ACCESS_TOKEN]
                )
            except AssertionError:
                if not (user_input[CONF_USERNAME] and user_input[CONF_ACCESS_TOKEN]):
                    _LOGGER.error("Failed to initialize FreeClient")
                    errors["base"] = "client_initialization_failed"
                else:
                    # Re-raise if credentials were provided but assertion still failed
                    # This indicates a programming error, not user input issue
                    raise

            # Send a test SMS to validate the credentials
            # The freesms library uses requests which can raise RequestException
            # for network issues (connection error, timeout, HTTP errors)
            if not errors and client:
                try:
                    response = await self.hass.async_add_executor_job(
                        client.send_sms, "Home Assistant test"
                    )
                    # Treat any non-success response as a validation failure so
                    # we do not create an entry when the API rejected the test SMS.
                    if response.status_code != HTTPStatus.OK:
                        if response.status_code == HTTPStatus.FORBIDDEN:
                            _LOGGER.error("Authentication failed: 403 Forbidden")
                            errors["base"] = "authentication_failed"
                        else:
                            _LOGGER.error(
                                "Test SMS failed with unexpected status: %s",
                                response.status_code,
                            )
                            errors["base"] = "test_sms_failed"
                except requests.exceptions.RequestException:
                    _LOGGER.exception("Failed to send test SMS")
                    errors["base"] = "test_sms_failed"
                except AssertionError:
                    # Re-raise unexpected AssertionErrors to avoid masking programming errors
                    raise

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_USERNAME): str,
                            vol.Required(CONF_ACCESS_TOKEN): str,
                        }
                    ),
                    errors=errors,
                )

            return self.async_create_entry(
                title=f"Free Mobile ({user_input[CONF_USERNAME]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import config from YAML."""
        await self.async_set_unique_id(import_data[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        # Validate credentials without sending a test SMS to avoid spamming
        # the user on every Home Assistant restart
        try:
            FreeClient(import_data[CONF_USERNAME], import_data[CONF_ACCESS_TOKEN])
        except AssertionError:
            if not (import_data[CONF_USERNAME] and import_data[CONF_ACCESS_TOKEN]):
                _LOGGER.error("Failed to initialize FreeClient")
                return self.async_abort(reason="client_initialization_failed")
            raise

        return self.async_create_entry(
            title=f"Free Mobile ({import_data[CONF_USERNAME]})",
            data=import_data,
        )
