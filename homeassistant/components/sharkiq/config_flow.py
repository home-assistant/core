# Config flow for Shark IQ integration.

import asyncio
from collections.abc import Mapping
from typing import Any

import aiohttp
from .sharkiq_pypi.sharkiq import SharkIqAuthError, SharkIqAuthVerificationRequiredError, get_ayla_api
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    API_BACKEND_AYLA,
    API_BACKEND_SKEGOX,
    CONF_API_BACKEND,
    DOMAIN,
    LOGGER,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_OPTIONS,
)

from .skegox_api import SkegoxApi
from .skegox_auth import (
    SkegoxAuthError,
    SkegoxAuthManager,
    SkegoxAuthRequiresVerificationError,
)

SHARKIQ_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION, default=SHARKIQ_REGION_DEFAULT):
            selector.SelectSelector(selector.SelectSelectorConfig(options=SHARKIQ_REGION_OPTIONS, translation_key="region"),
        ),
    }
)

# Validate Skegox API access:
# Returns info dict ``{"title": username, "backend": "skegox"}`` on success.
# Returns None if auth fails, verification is required, or no devices are found.
async def _validate_skegox(hass: HomeAssistant, config_entry: ConfigEntry | None, data: Mapping[str, Any]) -> dict[str, str] | None:
    region = data[CONF_REGION]
    auth_manager = SkegoxAuthManager(hass, config_entry, data[CONF_USERNAME], data[CONF_PASSWORD], region)

    try:
        await auth_manager.ensure_authenticated()
    except SkegoxAuthRequiresVerificationError:
        LOGGER.debug("Skegox auth requires verification (MFA/CAPTCHA)")
        await auth_manager.close()
        return None
    except SkegoxAuthError:
        LOGGER.debug("Skegox auth failed")
        await auth_manager.close()
        return None

    skegox_api = SkegoxApi(auth_manager)

    try:
        await skegox_api.discover()
        devices = await skegox_api.list_devices()
    except Exception:
        LOGGER.debug("Skegox device discovery failed", exc_info=True)
        await skegox_api.close()
        return None

    await skegox_api.close()

    if not devices:
        LOGGER.debug("Skegox returned no devices")
        return None

    return {"title": data[CONF_USERNAME], "backend": API_BACKEND_SKEGOX}

# Validate Ayla API access.
async def _validate_ayla(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, str]:
    new_websession = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True, quote_cookie=False),)
    ayla_api = get_ayla_api(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        websession=new_websession,
        europe=(data[CONF_REGION] == SHARKIQ_REGION_EUROPE),)

    try:
        async with asyncio.timeout(15):
            LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    # SharkNinja anti-bot protection triggered — not a credential issue
    except SharkIqAuthVerificationRequiredError:
        LOGGER.error(
            "SharkNinja is blocking automated login (anti-bot protection)."
            "Sign in with mobile app (account / password) only,"
            "do not use biometric credential storage."
        )
        raise RequiresVerification("SharkNinja is blocking automated login.") from None
    # Network or protocol-level failures
    except (TimeoutError, aiohttp.ClientError, TypeError) as error:
        LOGGER.error(error)
        raise CannotConnect("Unable to connect to SharkIQ services.  Check your region settings.") from error
    # Wrong username/password
    except SharkIqAuthError as error:
        LOGGER.error(error)
        raise InvalidAuth("Username or password incorrect.  Please check your credentials.") from error
    # Any other unexpected error — likely region misconfiguration
    except Exception as error:
        LOGGER.exception("Unexpected exception")
        raise UnknownAuth("An unknown error occurred. Check your region settings and open an issue on GitHub if the issue persists.") from error

    return {"title": data[CONF_USERNAME], "backend": API_BACKEND_AYLA}

# Validate the user input allows us to connect. Tries Skegox first, falls back to Ayla.
async def _validate_input(hass: HomeAssistant, config_entry: ConfigEntry | None, data: Mapping[str, Any]) -> dict[str, str]:
    # Try Skegox first
    skegox_result = await _validate_skegox(hass, config_entry, data)
    if skegox_result:
        return skegox_result

    # Fall back to Ayla
    return await _validate_ayla(hass, data)

# Handle a config flow for Shark IQ.
class SharkIqConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    # Validate form input.
    async def _async_validate_input(self, user_input: Mapping[str, Any]) -> tuple[dict[str, str] | None, dict[str, str]]:
        errors = {}
        info = None

        try:
            info = await _validate_input(self.hass, None, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except UnknownAuth:
            errors["base"] = "unknown"
        except RequiresVerification:
            errors["base"] = "requires_verification"
        return info, errors

    # Handle the initial step.
    async def async_step_user(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._async_validate_input(user_input)
            if info:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                entry_data = {**user_input, CONF_API_BACKEND: info["backend"]}
                return self.async_create_entry(title=info["title"], data=entry_data)

        return self.async_show_form(step_id="user", data_schema=SHARKIQ_SCHEMA, errors=errors)

    # Handle re-auth if login is invalid.
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    # Handle a flow initiated by reauthentication.
    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            info, errors = await self._async_validate_input(user_input)

            if not errors and info:
                if entry := await self.async_set_unique_id(self.unique_id):
                    updated_data = {**user_input, CONF_API_BACKEND: info["backend"]}
                    self.hass.config_entries.async_update_entry(entry, data=updated_data)
                    return self.async_abort(reason="reauth_successful")

            if errors.get("base") and errors["base"] != "invalid_auth":
                return self.async_abort(reason=errors["base"])

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SHARKIQ_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class UnknownAuth(HomeAssistantError):
    """Error to indicate there is an uncaught auth error."""

class RequiresVerification(HomeAssistantError):
    """Error to indicate account verification is required."""    