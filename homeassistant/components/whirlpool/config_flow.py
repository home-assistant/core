"""Config flow for Whirlpool Appliances integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol
from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import AccountLockedError as WhirlpoolAccountLocked, Auth
from whirlpool.backendselector import BackendSelector

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BRANDS_CONF_MAP, CONF_BRAND, DOMAIN, REGIONS_CONF_MAP

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION): vol.In(list(REGIONS_CONF_MAP)),
        vol.Required(CONF_BRAND): vol.In(list(BRANDS_CONF_MAP)),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_BRAND): vol.In(list(BRANDS_CONF_MAP)),
    }
)


async def authenticate(
    hass: HomeAssistant, data: dict[str, str], check_appliances_exist: bool
) -> str | None:
    """Authenticate with the api.

    data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    Returns the error translation key if authentication fails, or None on success.
    """
    session = async_get_clientsession(hass)
    region = REGIONS_CONF_MAP[data[CONF_REGION]]
    brand = BRANDS_CONF_MAP[data[CONF_BRAND]]
    backend_selector = BackendSelector(brand, region)
    auth = Auth(backend_selector, data[CONF_USERNAME], data[CONF_PASSWORD], session)

    try:
        await auth.do_auth()
    except WhirlpoolAccountLocked:
        return "account_locked"
    except (TimeoutError, ClientError):
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"

    if not auth.is_access_token_valid():
        return "invalid_auth"

    if check_appliances_exist:
        appliances_manager = AppliancesManager(backend_selector, auth, session)
        await appliances_manager.fetch_appliances()

        if not appliances_manager.aircons and not appliances_manager.washer_dryers:
            return "no_appliances"

    return None


class WhirlpoolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Whirlpool Sixth Sense."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Whirlpool Sixth Sense."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Whirlpool Sixth Sense."""
        errors: dict[str, str] = {}

        if user_input:
            reauth_entry = self._get_reauth_entry()
            password = user_input[CONF_PASSWORD]
            brand = user_input[CONF_BRAND]
            data = {**reauth_entry.data, CONF_PASSWORD: password, CONF_BRAND: brand}

            error_key = await authenticate(self.hass, data, False)
            if not error_key:
                return self.async_update_reload_and_abort(reauth_entry, data=data)
            errors["base"] = error_key

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"name": "Whirlpool"},
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        error_key = await authenticate(self.hass, user_input, True)
        if not error_key:
            await self.async_set_unique_id(
                user_input[CONF_USERNAME].lower(), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_USERNAME], data=user_input
            )

        errors = {"base": error_key}
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
