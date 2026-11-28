"""Config flow for the Evohome integration."""

from collections.abc import Mapping
import logging
from typing import Any, Final, override

import evohomeasync2 as ec2
from evohomeasync2.const import SZ_USER_ID
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .storage import TokenManager

_LOGGER = logging.getLogger(__name__)

_USERNAME_SELECTOR: Final = TextSelector(
    TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
)
_PASSWORD_SELECTOR: Final = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

STEP_USER_DATA_SCHEMA: Final = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): _USERNAME_SELECTOR,
        probatio.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
    }
)
STEP_REAUTH_DATA_SCHEMA: Final = probatio.Schema(
    {probatio.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}
)


class _NoSystemsError(Exception):
    """The account has no location with a temperature control system."""


async def _async_get_user_id(hass: HomeAssistant, username: str, password: str) -> str:
    """Log in with the credentials, and return the account's user id.

    The new tokens are cached, so the config entry's setup doesn't log in again.
    """

    token_manager = TokenManager(
        hass, username, password, async_get_clientsession(hass), use_cache=False
    )
    client = ec2.EvohomeClient(token_manager)

    await client.setup()

    if not any(loc.tcs for loc in client.locations):
        raise _NoSystemsError

    return client.user_account[SZ_USER_ID]


class EvohomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for evohome."""

    VERSION = 1

    async def _async_validate(
        self, username: str, password: str
    ) -> tuple[str | None, str | None]:
        """Check the credentials, and return the user id or the reason they failed."""

        try:
            user_id = await _async_get_user_id(self.hass, username, password)
        except ec2.BadUserCredentialsError:
            return None, "invalid_auth"
        except ec2.ApiCallFailedError, ec2.BadApiResponseError:
            return None, "cannot_connect"
        except _NoSystemsError:
            return None, "no_systems"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return user_id, None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            user_id, error = await self._async_validate(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the configuration from configuration.yaml."""

        user_id, error = await self._async_validate(
            import_data[CONF_USERNAME], import_data[CONF_PASSWORD]
        )
        if error is not None:
            return self.async_abort(reason=error)

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data[CONF_USERNAME], data=import_data
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth, after the vendor refused the credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password of the account again."""

        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            user_id, error = await self._async_validate(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the credentials of the account (e.g. after its email changed)."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            user_id, error = await self._async_validate(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error is None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry, title=user_input[CONF_USERNAME], data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {CONF_USERNAME: entry.data[CONF_USERNAME]},
            ),
            errors=errors,
        )
