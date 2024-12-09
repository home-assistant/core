"""Config flow for habitica integration."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from habitipy.aio import HabitipyAsync
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import HabiticaConfigEntry
from .const import (
    CONF_API_USER,
    DEFAULT_URL,
    DOMAIN,
    FORGOT_PASSWORD_URL,
    HABITICANS_URL,
    SECTION_REAUTH_API_KEY,
    SECTION_REAUTH_LOGIN,
    SIGN_UP_URL,
    SITE_DATA_URL,
)

STEP_ADVANCED_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_USER): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(SECTION_REAUTH_LOGIN): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.EMAIL,
                            autocomplete="email",
                        )
                    ),
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                },
            ),
            {"collapsed": False},
        ),
        vol.Required(SECTION_REAUTH_API_KEY): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_API_KEY): str,
                },
            ),
            {"collapsed": True},
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


class HabiticaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitica."""

    VERSION = 1
    reauth_entry: HabiticaConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        return self.async_show_menu(
            step_id="user",
            menu_options=["login", "advanced"],
            description_placeholders={
                "signup": SIGN_UP_URL,
                "habiticans": HABITICANS_URL,
            },
        )

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Config flow with username/password.

        Simplified configuration setup that retrieves API credentials
        from Habitica.com by authenticating with login and password.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, login_response = await self.validate_login(
                {**user_input, CONF_URL: DEFAULT_URL}
            )

            if not errors and login_response is not None:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=login_response["username"],
                    data={
                        CONF_API_USER: login_response["id"],
                        CONF_API_KEY: login_response["apiToken"],
                        CONF_USERNAME: login_response["username"],
                        CONF_URL: DEFAULT_URL,
                        CONF_VERIFY_SSL: True,
                    },
                )

        return self.async_show_form(
            step_id="login",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_LOGIN_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={"forgot_password": FORGOT_PASSWORD_URL},
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Advanced configuration with User Id and API Token.

        Advanced configuration allows connecting to Habitica instances
        hosted on different domains or to self-hosted instances.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, api_response = await self.validate_api_key(user_input)
            if not errors and api_response is not None:
                await self.async_set_unique_id(user_input[CONF_API_USER])
                self._abort_if_unique_id_configured()
                user_input[CONF_USERNAME] = api_response["auth"]["local"]["username"]
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="advanced",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_ADVANCED_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={
                "site_data": SITE_DATA_URL,
                "default_url": DEFAULT_URL,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self._get_reauth_entry()

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[SECTION_REAUTH_LOGIN].get(CONF_USERNAME) and user_input[
                SECTION_REAUTH_LOGIN
            ].get(CONF_PASSWORD):
                errors, response = await self.validate_login(
                    {**self.reauth_entry.data, **user_input[SECTION_REAUTH_LOGIN]}
                )
                if not errors and response is not None:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self.reauth_entry,
                        data={
                            **self.reauth_entry.data,
                            CONF_API_KEY: response["apiToken"],
                        },
                    )
            elif user_input[SECTION_REAUTH_API_KEY].get(CONF_API_KEY):
                errors, response = await self.validate_api_key(
                    {
                        **self.reauth_entry.data,
                        CONF_API_KEY: user_input[SECTION_REAUTH_API_KEY][CONF_API_KEY],
                    }
                )
                if not errors and response is not None:
                    return self.async_update_reload_and_abort(
                        self.reauth_entry,
                        data={
                            **self.reauth_entry.data,
                            CONF_API_KEY: user_input[SECTION_REAUTH_API_KEY][
                                CONF_API_KEY
                            ],
                        },
                    )
            else:
                errors["base"] = "invalid_credentials"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                suggested_values={
                    CONF_USERNAME: (
                        user_input[SECTION_REAUTH_LOGIN].get(CONF_USERNAME)
                        if user_input
                        else None,
                    )
                },
            ),
            description_placeholders={
                CONF_NAME: self.reauth_entry.title,
                "habiticans": HABITICANS_URL,
            },
            errors=errors,
        )

    async def validate_login(
        self, user_input: Mapping[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate login with login credentials."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, True)
        )
        api = await self.hass.async_add_executor_job(
            HabitipyAsync,
            {
                "login": "",
                "password": "",
                "url": user_input.get(CONF_URL, DEFAULT_URL),
            },
        )
        try:
            login_response = await api.user.auth.local.login.post(
                session=session,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
        except ClientResponseError as ex:
            if ex.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(login_response["id"])
            return errors, login_response

        return errors, None

    async def validate_api_key(
        self, user_input: Mapping[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate authentication with api key."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, True)
        )
        api = await self.hass.async_add_executor_job(
            HabitipyAsync,
            {
                "login": user_input[CONF_API_USER],
                "password": user_input[CONF_API_KEY],
                "url": user_input.get(CONF_URL, DEFAULT_URL),
            },
        )
        try:
            login_response = await api.user.get(
                session=session,
                userFields="auth",
            )
        except ClientResponseError as ex:
            if ex.status == HTTPStatus.UNAUTHORIZED:
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_API_USER])
            return errors, login_response

        return errors, None
