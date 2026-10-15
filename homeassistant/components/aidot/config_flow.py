"""Config flow for Aidot integration."""

from collections.abc import Mapping
from typing import Any, override

from aidot.client import AidotClient
from aidot.const import CONF_ID, DEFAULT_COUNTRY_CODE, SUPPORTED_COUNTRY_CODES
from aidot.exceptions import AidotUserOrPassIncorrect
from aiohttp import ClientError
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_EFFECT_SOURCE,
    DEFAULT_EFFECT_SOURCE,
    DOMAIN,
    EFFECT_SOURCE_ALL,
    EFFECT_SOURCE_RECOMMENDED,
)

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_COUNTRY_CODE,
            default=DEFAULT_COUNTRY_CODE,
        ): selector.CountrySelector(
            selector.CountrySelectorConfig(
                countries=SUPPORTED_COUNTRY_CODES,
            )
        ),
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

REAUTH_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
)


def _effect_source_schema(default: str = DEFAULT_EFFECT_SOURCE) -> probatio.Schema:
    """Return schema for effect source selection."""
    return probatio.Schema(
        {
            probatio.Required(
                CONF_EFFECT_SOURCE,
                default=default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=EFFECT_SOURCE_ALL,
                            label="All effects",
                        ),
                        selector.SelectOptionDict(
                            value=EFFECT_SOURCE_RECOMMENDED,
                            label="Recommended effects",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


EFFECT_SOURCE_SCHEMA = _effect_source_schema()


class AidotOptionsFlowHandler(OptionsFlow):
    """Handle Aidot options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Aidot options."""
        if user_input is not None:
            if (
                coordinator := getattr(self.config_entry, "runtime_data", None)
            ) is not None:
                coordinator.update_options(user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_effect_source_schema(
                self.config_entry.options.get(CONF_EFFECT_SOURCE, DEFAULT_EFFECT_SOURCE)
            ),
            errors={},
        )


class AidotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle aidot config flow."""

    _login_info: dict[str, Any]
    _title: str

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AidotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AidotOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = AidotClient(
                session=async_get_clientsession(self.hass),
                country_code=user_input[CONF_COUNTRY_CODE],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            login_info, errors = await self._async_login(client)
            if login_info is not None:
                await self.async_set_unique_id(login_info[CONF_ID])
                self._abort_if_unique_id_configured()
                self._login_info = login_info
                self._title = (
                    f"{user_input[CONF_USERNAME]} {user_input[CONF_COUNTRY_CODE]}"
                )
                return await self.async_step_effect_source()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_effect_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle effect source selection."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data=self._login_info,
                options={
                    CONF_EFFECT_SOURCE: user_input[CONF_EFFECT_SOURCE],
                },
            )

        return self.async_show_form(
            step_id="effect_source",
            data_schema=EFFECT_SOURCE_SCHEMA,
            errors={},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            client = AidotClient(
                session=async_get_clientsession(self.hass),
                token=dict(reauth_entry.data),
            )
            client.update_password(user_input[CONF_PASSWORD])
            login_info, errors = await self._async_login(client)
            if login_info is not None:
                await self.async_set_unique_id(login_info[CONF_ID])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=login_info
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
        )

    async def _async_login(
        self, client: AidotClient
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Log in and return the login info or the errors."""
        try:
            login_info = await client.async_post_login()
        except AidotUserOrPassIncorrect:
            return None, {"base": "invalid_auth"}
        except TimeoutError, ClientError:
            return None, {"base": "cannot_connect"}
        finally:
            # The client starts LAN discovery once it has login info
            await client.async_cleanup()
        return login_info, {}
