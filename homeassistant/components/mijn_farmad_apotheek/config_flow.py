"""Config flow for the Mijn Farmad Apotheek integration."""

import logging
from typing import Any, override

from aiofarmad import (
    FarmadAccount,
    FarmadAuthenticationError,
    FarmadClient,
    FarmadError,
    FarmadMfaRequiredError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def _async_login(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[FarmadAccount, str, str | None]:
    """Log in with the given credentials and return the account and token pair."""
    client = FarmadClient(
        session=async_get_clientsession(hass),
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
    )
    try:
        await client.async_login()
        account = await client.async_get_account()
        if (access_token := client.access_token) is None:
            raise FarmadAuthenticationError("Login returned no access token")
        return account, access_token, client.refresh_token
    finally:
        await client.async_close()


class FarmadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Mijn Farmad Apotheek config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                account, access_token, refresh_token = await _async_login(
                    self.hass, user_input
                )
            except FarmadMfaRequiredError:
                errors["base"] = "mfa_required"
            except FarmadAuthenticationError:
                errors["base"] = "invalid_auth"
            except FarmadError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(account.id)
                return self.async_create_entry(
                    title=account.full_name,
                    data={
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
