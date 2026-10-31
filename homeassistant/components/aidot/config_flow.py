"""Config flow for Aidot integration."""

from collections.abc import Mapping
from typing import Any, override

from aidot.client import AidotClient
from aidot.const import CONF_ID, DEFAULT_COUNTRY_CODE, SUPPORTED_COUNTRY_CODES
from aidot.exceptions import AidotUserOrPassIncorrect
from aiohttp import ClientError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

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


class AidotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle aidot config flow."""

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
                return self.async_create_entry(
                    title=f"{user_input[CONF_USERNAME]} {user_input[CONF_COUNTRY_CODE]}",
                    data=login_info,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
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
