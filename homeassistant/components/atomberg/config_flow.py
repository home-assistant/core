"""Config flow for Atomberg."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AtombergAuthError, AtombergClient, AtombergError
from .const import CONF_REFRESH_TOKEN, DOMAIN, LOGGER

PORTAL_URL = "https://developer.atomberg-iot.com"

CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Required(probatio.Secret(CONF_REFRESH_TOKEN)): cv.string,
    }
)


class AtombergConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atomberg."""

    VERSION = 1

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        client = AtombergClient(
            async_get_clientsession(self.hass),
            user_input[CONF_API_KEY],
            user_input[CONF_REFRESH_TOKEN],
        )
        try:
            await client.async_get_devices()
        except AtombergAuthError:
            return {"base": "invalid_auth"}
        except AtombergError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(title="Atomberg", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, user_input
            ),
            description_placeholders={"portal_url": PORTAL_URL},
            errors=errors,
        )

    @override
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
        )
