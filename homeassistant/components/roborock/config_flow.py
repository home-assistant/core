"""Config flow for Roborock."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any

from roborock.containers import UserData
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockTooFrequentCodeRequests,
    RoborockUrlException,
)
from roborock.web_api import RoborockApiClient
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback

from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_CODE,
    CONF_USER_DATA,
    DEFAULT_DRAWABLES,
    DOMAIN,
    DRAWABLES,
)

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._client: RoborockApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            self._username = username
            _LOGGER.debug("Requesting code for Roborock account")
            self._client = RoborockApiClient(username)
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            errors=errors,
        )

    async def _request_code(self) -> dict:
        assert self._client
        errors: dict[str, str] = {}
        try:
            await self._client.request_code()
        except RoborockAccountDoesNotExist:
            errors["base"] = "invalid_email"
        except RoborockUrlException:
            errors["base"] = "unknown_url"
        except RoborockInvalidEmail:
            errors["base"] = "invalid_email_format"
        except RoborockTooFrequentCodeRequests:
            errors["base"] = "too_frequent_code_requests"
        except RoborockException:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown_roborock"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors

    async def async_step_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self._client
        assert self._username
        if user_input is not None:
            code = user_input[CONF_ENTRY_CODE]
            _LOGGER.debug("Logging into Roborock account using email provided code")
            try:
                login_data = await self._client.code_login(code)
            except RoborockInvalidCode:
                errors["base"] = "invalid_code"
            except RoborockException:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown_roborock"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    reauth_entry = self._get_reauth_entry()
                    self.hass.config_entries.async_update_entry(
                        reauth_entry,
                        data={
                            **reauth_entry.data,
                            CONF_USER_DATA: login_data.as_dict(),
                        },
                    )
                    return self.async_abort(reason="reauth_successful")
                return self._create_entry(self._client, self._username, login_data)

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required(CONF_ENTRY_CODE): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._username = entry_data[CONF_USERNAME]
        assert self._username
        self._client = RoborockApiClient(self._username)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._request_code()
            if not errors:
                return await self.async_step_code()
        return self.async_show_form(step_id="reauth_confirm", errors=errors)

    def _create_entry(
        self, client: RoborockApiClient, username: str, user_data: UserData
    ) -> ConfigFlowResult:
        """Finished config flow and create entry."""
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_USER_DATA: user_data.as_dict(),
                CONF_BASE_URL: client.base_url,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RoborockOptionsFlowHandler:
        """Create the options flow."""
        return RoborockOptionsFlowHandler(config_entry)


class RoborockOptionsFlowHandler(OptionsFlow):
    """Handle an option flow for Roborock."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = deepcopy(dict(config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_drawables()

    async def async_step_drawables(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the map object drawable options."""
        if user_input is not None:
            self.options.setdefault(DRAWABLES, {}).update(user_input)
            return self.async_create_entry(title="", data=self.options)
        data_schema = {}
        for drawable, default_value in DEFAULT_DRAWABLES.items():
            data_schema[
                vol.Required(
                    drawable.value,
                    default=self.config_entry.options.get(DRAWABLES, {}).get(
                        drawable, default_value
                    ),
                )
            ] = bool
        return self.async_show_form(
            step_id=DRAWABLES,
            data_schema=vol.Schema(data_schema),
        )
