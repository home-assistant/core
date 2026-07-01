"""Config flow for Synology SRM integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import requests
import synology_srm
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_PORT, DEFAULT_SSL, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SynologySRMFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Synology SRM config flow."""

    VERSION = 1

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Test the connection. Return an error key on failure, None on success."""
        try:
            api = synology_srm.Client(
                host=data[CONF_HOST],
                port=data[CONF_PORT],
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
                https=data[CONF_SSL],
            )
            if not data[CONF_VERIFY_SSL]:
                api.http.disable_https_verify()
            await self.hass.async_add_executor_job(api.mesh.get_system_info)
        except requests.exceptions.SSLError as err:
            _LOGGER.error("SSL error: %s", err)
            return "ssl_error"
        except requests.exceptions.HTTPError as err:
            _LOGGER.error("Login failed: %s", err)
            return "cannot_connect"
        except (
            synology_srm.http.SynologyApiError,
            synology_srm.http.SynologyHttpException,
        ) as err:
            _LOGGER.error("Login failed: %s", err)
            return "invalid_auth"
        except Exception:
            _LOGGER.exception(
                "Unknown error connecting with Synology SRM: %s", data[CONF_HOST]
            )
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if (error := await self._async_validate(user_input)) is not None:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"{DOMAIN} ({user_input[CONF_HOST]})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                    vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}
            if (error := await self._async_validate(user_input)) is not None:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )
