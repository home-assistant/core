"""Config flow for EvolvIOT."""

from typing import Any, override

from pyevolviot import (
    EvolvIOTApi,
    EvolvIOTApiError,
    EvolvIOTAuthError,
    EvolvIOTConnectionError,
    EvolvIOTDeviceAuthorizationDenied,
    EvolvIOTDeviceAuthorizationExpired,
    EvolvIOTDeviceAuthorizationPending,
    normalize_api_base_url,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_API_BASE_URL,
    DOMAIN,
    NAME,
)


def _pair_schema() -> vol.Schema:
    return vol.Schema({})


class EvolvIOTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EvolvIOT config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_base_url = DEFAULT_API_BASE_URL
        self._verify_ssl = True
        self._pairing: dict[str, Any] = {}

    def _api(self, access_token: str = "", refresh_token: str = "") -> EvolvIOTApi:
        """Return an EvolvIOT API client."""
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        return EvolvIOTApi(
            session,
            self._api_base_url,
            access_token,
            refresh_token=refresh_token,
            verify_ssl=self._verify_ssl,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start app-based pairing."""
        self._api_base_url = normalize_api_base_url(self._api_base_url)

        try:
            self._pairing = await self._api().async_start_device_authorization()
        except EvolvIOTConnectionError:
            return self.async_show_form(
                step_id="user",
                data_schema=_pair_schema(),
                errors={"base": "cannot_connect"},
            )
        except EvolvIOTApiError:
            return self.async_show_form(
                step_id="user",
                data_schema=_pair_schema(),
                errors={"base": "unknown"},
            )

        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show pairing details and finish after app approval."""
        errors: dict[str, str] = {}

        if not self._pairing:
            return await self.async_step_user()

        if user_input is not None:
            device_code = str(self._pairing["device_code"])
            try:
                token_data = await self._api().async_exchange_device_code(device_code)
                access_token = str(token_data.get("access_token") or "").strip()
                refresh_token = str(token_data.get("refresh_token") or "").strip()
                data = await self._api(
                    access_token, refresh_token
                ).async_validate_data()
            except EvolvIOTDeviceAuthorizationPending:
                errors["base"] = "authorization_pending"
            except EvolvIOTDeviceAuthorizationExpired:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_pair_schema(),
                    errors={"base": "authorization_expired"},
                )
            except EvolvIOTDeviceAuthorizationDenied:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_pair_schema(),
                    errors={"base": "authorization_denied"},
                )
            except EvolvIOTAuthError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_pair_schema(),
                    errors={"base": "invalid_auth"},
                )
            except EvolvIOTConnectionError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = data.user_id or self._api_base_url
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=NAME,
                    data={
                        CONF_API_BASE_URL: self._api_base_url,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_VERIFY_SSL: self._verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="pair",
            data_schema=_pair_schema(),
            errors=errors,
            description_placeholders=self._pair_description_placeholders(),
        )

    def _pair_description_placeholders(self) -> dict[str, str]:
        """Return placeholders shown in the pairing form step."""
        return {
            "user_code": str(self._pairing.get("user_code") or ""),
            "expires_in": str(self._pairing.get("expires_in") or ""),
        }
