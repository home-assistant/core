"""Config flow for habitica integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from habiticalib import (
    Habitica,
    HabiticaException,
    LoginData,
    NotAuthorizedError,
    UserData,
)
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
            errors, login, user = await self.validate_login(
                {**user_input, CONF_URL: DEFAULT_URL}
            )
            if not errors and login is not None and user is not None:
                await self.async_set_unique_id(str(login.id))
                self._abort_if_unique_id_configured()
                if TYPE_CHECKING:
                    assert user.profile.name
                return self.async_create_entry(
                    title=user.profile.name,
                    data={
                        CONF_API_USER: str(login.id),
                        CONF_API_KEY: login.apiToken,
                        CONF_NAME: user.profile.name,  # needed for api_call action
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
            await self.async_set_unique_id(user_input[CONF_API_USER])
            self._abort_if_unique_id_configured()
            errors, user = await self.validate_api_key(user_input)
            if not errors and user is not None:
                if TYPE_CHECKING:
                    assert user.profile.name
                return self.async_create_entry(
                    title=user.profile.name,
                    data={
                        **user_input,
                        CONF_URL: user_input.get(CONF_URL, DEFAULT_URL),
                        CONF_NAME: user.profile.name,  # needed for api_call action
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry: HabiticaConfigEntry = self._get_reauth_entry()

        if user_input is not None:
            if user_input[SECTION_REAUTH_LOGIN].get(CONF_USERNAME) and user_input[
                SECTION_REAUTH_LOGIN
            ].get(CONF_PASSWORD):
                errors, login, _ = await self.validate_login(
                    {**reauth_entry.data, **user_input[SECTION_REAUTH_LOGIN]}
                )
                if not errors and login is not None:
                    await self.async_set_unique_id(str(login.id))
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={CONF_API_KEY: login.apiToken},
                    )
            elif user_input[SECTION_REAUTH_API_KEY].get(CONF_API_KEY):
                errors, user = await self.validate_api_key(
                    {
                        **reauth_entry.data,
                        **user_input[SECTION_REAUTH_API_KEY],
                    }
                )
                if not errors and user is not None:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input[SECTION_REAUTH_API_KEY]
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
                CONF_NAME: reauth_entry.title,
                "habiticans": HABITICANS_URL,
            },
            errors=errors,
        )

    async def validate_login(
        self, user_input: Mapping[str, Any]
    ) -> tuple[dict[str, str], LoginData | None, UserData | None]:
        """Validate login with login credentials."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, True)
        )
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
            return errors, login.data, user.data

        return errors, None, None

    async def validate_api_key(
        self, user_input: Mapping[str, Any]
    ) -> tuple[dict[str, str], UserData | None]:
        """Validate authentication with api key."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(
            self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, True)
        )
        api = Habitica(
            session=session,
            x_client=X_CLIENT,
            api_user=user_input[CONF_API_USER],
            api_key=user_input[CONF_API_KEY],
            url=user_input.get(CONF_URL, DEFAULT_URL),
        )
        try:
            user = await api.get_user(user_fields="profile")
        except NotAuthorizedError:
            errors["base"] = "invalid_auth"
        except (HabiticaException, ClientError):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return errors, user.data

        return errors, None
