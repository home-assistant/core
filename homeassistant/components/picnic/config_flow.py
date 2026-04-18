"""Config flow for Picnic integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from python_picnic_api2 import PicnicAPI
from python_picnic_api2.session import (
    Picnic2FAError,
    Picnic2FARequired,
    PicnicAuthError,
)
import requests
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_COUNTRY_CODE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import COUNTRY_CODES, DOMAIN, TWO_FA_CHANNELS

_LOGGER = logging.getLogger(__name__)

CONF_2FA_CODE = "two_fa_code"
CONF_2FA_CHANNEL = "two_fa_channel"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_COUNTRY_CODE, default=COUNTRY_CODES[0]): vol.In(
            COUNTRY_CODES
        ),
    }
)

STEP_2FA_CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_2FA_CHANNEL, default=TWO_FA_CHANNELS[0]): SelectSelector(
            SelectSelectorConfig(
                options=TWO_FA_CHANNELS,
                mode=SelectSelectorMode.LIST,
                translation_key="two_fa_channel",
            )
        ),
    }
)

STEP_2FA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_2FA_CODE): str,
    }
)


class PicnicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Picnic."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._picnic: PicnicAPI | None = None
        self._user_input: dict[str, Any] = {}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform the re-auth step upon an API authentication error."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await self.hass.async_add_executor_job(
                self._start_login,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY_CODE],
            )
        except Picnic2FARequired:
            self._user_input = user_input
            return await self.async_step_2fa_channel()
        except requests.exceptions.ConnectionError:
            errors["base"] = "cannot_connect"
        except PicnicAuthError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self._async_finish(user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    def _start_login(self, username: str, password: str, country_code: str) -> None:
        self._picnic = PicnicAPI(country_code=country_code)
        self._picnic.login(username, password)

    async def async_step_2fa_channel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick the 2FA delivery channel."""
        assert self._picnic is not None

        if user_input is None:
            return self.async_show_form(
                step_id="2fa_channel", data_schema=STEP_2FA_CHANNEL_SCHEMA
            )

        errors = {}
        channel = user_input[CONF_2FA_CHANNEL].upper()
        try:
            await self.hass.async_add_executor_job(
                self._picnic.generate_2fa_code, channel
            )
        except requests.exceptions.ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Failed to request 2FA code via %s", channel)
            errors["base"] = "unknown"
        else:
            return await self.async_step_2fa()

        return self.async_show_form(
            step_id="2fa_channel",
            data_schema=STEP_2FA_CHANNEL_SCHEMA,
            errors=errors,
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the 2FA verification step."""
        assert self._picnic is not None

        if user_input is None:
            return self.async_show_form(step_id="2fa", data_schema=STEP_2FA_SCHEMA)

        errors = {}

        try:
            await self.hass.async_add_executor_job(
                self._picnic.verify_2fa_code, user_input[CONF_2FA_CODE]
            )
        except Picnic2FAError:
            errors["base"] = "invalid_2fa_code"
        except requests.exceptions.ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during 2FA verification")
            errors["base"] = "unknown"
        else:
            return await self._async_finish(self._user_input)

        return self.async_show_form(
            step_id="2fa", data_schema=STEP_2FA_SCHEMA, errors=errors
        )

    async def _async_finish(
        self,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Finalize the config entry after successful authentication."""
        assert self._picnic is not None

        auth_token = self._picnic.session.auth_token
        user_data = await self.hass.async_add_executor_job(self._picnic.get_user)

        data = {
            CONF_ACCESS_TOKEN: auth_token,
            CONF_COUNTRY_CODE: user_input[CONF_COUNTRY_CODE],
        }
        existing_entry = await self.async_set_unique_id(user_data["user_id"])

        # Abort if we're adding a new config and the unique id is already in use, else create the entry
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Picnic", data=data)

        # In case of re-auth, only continue if an exiting account exists with the same unique id
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": "different_account"},
        )
