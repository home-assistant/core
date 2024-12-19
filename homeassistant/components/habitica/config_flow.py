"""Config flow for habitica integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from habiticalib import Habitica, HabiticaException, NotAuthorizedError
import voluptuous as vol

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

from .const import (
    CONF_API_USER,
    DEFAULT_URL,
    DOMAIN,
    FORGOT_PASSWORD_URL,
    HABITICANS_URL,
    SIGN_UP_URL,
    SITE_DATA_URL,
    X_CLIENT,
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

_LOGGER = logging.getLogger(__name__)


class HabiticaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for habitica."""

    VERSION = 1

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
            session = async_get_clientsession(self.hass)
            api = Habitica(session=session, x_client=X_CLIENT)
            try:
                login = await api.login(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                user = await api.get_user(user_fields="profile")

            except NotAuthorizedError:
                errors["base"] = "invalid_auth"
            except (HabiticaException, ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(login.data.id))
                self._abort_if_unique_id_configured()
                if TYPE_CHECKING:
                    assert user.data.profile.name
                return self.async_create_entry(
                    title=user.data.profile.name,
                    data={
                        CONF_API_USER: str(login.data.id),
                        CONF_API_KEY: login.data.apiToken,
                        CONF_NAME: user.data.profile.name,  # needed for api_call action
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
            session = async_get_clientsession(
                self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
            )
            try:
                api = Habitica(
                    session=session,
                    x_client=X_CLIENT,
                    api_user=user_input[CONF_API_USER],
                    api_key=user_input[CONF_API_KEY],
                    url=user_input.get(CONF_URL, DEFAULT_URL),
                )
                user = await api.get_user(user_fields="profile")
            except NotAuthorizedError:
                errors["base"] = "invalid_auth"
            except (HabiticaException, ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_API_USER])
                self._abort_if_unique_id_configured()
                if TYPE_CHECKING:
                    assert user.data.profile.name
                return self.async_create_entry(
                    title=user.data.profile.name,
                    data={
                        **user_input,
                        CONF_URL: user_input.get(CONF_URL, DEFAULT_URL),
                        CONF_NAME: user.data.profile.name,  # needed for api_call action
                    },
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
