"""Config flow for EvolvIOT."""

import asyncio
from typing import TYPE_CHECKING, Any, override

from pyevolviot import (
    EvolvIOTApi,
    EvolvIOTApiError,
    EvolvIOTAuthError,
    EvolvIOTConnectionError,
    EvolvIOTData,
    EvolvIOTDeviceAuthorizationDenied,
    EvolvIOTDeviceAuthorizationExpired,
    EvolvIOTDeviceAuthorizationPending,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DEFAULT_API_BASE_URL, DOMAIN, NAME

type PairingResult = tuple[str, str, EvolvIOTData]


def _refresh_token_from_response(token_data: dict[str, Any]) -> str:
    """Return the refresh token from a token response."""
    refresh_token = token_data.get(CONF_REFRESH_TOKEN)
    if not isinstance(refresh_token, str) or not (
        refresh_token := refresh_token.strip()
    ):
        raise EvolvIOTApiError("Token response did not include refresh token")
    return refresh_token


class EvolvIOTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an EvolvIOT config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._verify_ssl = True
        self._pairing: dict[str, Any] = {}
        self._pairing_task: asyncio.Task[PairingResult] | None = None
        self._pairing_result: PairingResult | None = None

    def _api(self, access_token: str = "", refresh_token: str = "") -> EvolvIOTApi:
        """Return an EvolvIOT API client."""
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        return EvolvIOTApi(
            session,
            DEFAULT_API_BASE_URL,
            access_token,
            refresh_token=refresh_token,
            verify_ssl=self._verify_ssl,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start app-based pairing."""
        if not self._pairing:
            try:
                self._pairing = await self._api().async_start_device_authorization()
            except EvolvIOTConnectionError:
                return self.async_abort(reason="cannot_connect")
            except EvolvIOTApiError:
                return self.async_abort(reason="unknown")

            if not self._pairing.get("device_code") or not self._pairing.get(
                "user_code"
            ):
                return self.async_abort(reason="unknown")

        if self._pairing_task is None:
            self._pairing_task = self.hass.async_create_task(
                self._async_wait_for_pairing()
            )

        if self._pairing_task.done():
            if exception := self._pairing_task.exception():
                if isinstance(exception, EvolvIOTDeviceAuthorizationDenied):
                    next_step_id = "authorization_denied"
                elif isinstance(exception, EvolvIOTDeviceAuthorizationExpired):
                    next_step_id = "authorization_expired"
                elif isinstance(exception, EvolvIOTAuthError):
                    next_step_id = "invalid_auth"
                elif isinstance(exception, EvolvIOTConnectionError):
                    next_step_id = "cannot_connect"
                else:
                    next_step_id = "unknown"
                return self.async_show_progress_done(next_step_id=next_step_id)

            self._pairing_result = self._pairing_task.result()
            return self.async_show_progress_done(next_step_id="finish")

        return self.async_show_progress(
            step_id="user",
            progress_action="pair",
            description_placeholders=self._pair_description_placeholders(),
            progress_task=self._pairing_task,
        )

    async def _async_wait_for_pairing(self) -> PairingResult:
        """Wait for the user to approve device authorization."""
        device_code = str(self._pairing["device_code"])
        interval = self._pairing.get("interval", 5)
        while True:
            try:
                token_data = await self._api().async_exchange_device_code(device_code)
            except EvolvIOTDeviceAuthorizationPending:
                await asyncio.sleep(interval)
                continue
            break

        access_token = str(token_data[CONF_ACCESS_TOKEN]).strip()
        refresh_token = _refresh_token_from_response(token_data)
        data = await self._api(access_token, refresh_token).async_validate_data()
        if not data.user_id:
            raise EvolvIOTApiError("Account response did not include a user ID")
        return access_token, refresh_token, data

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after device authorization."""
        if TYPE_CHECKING:
            assert self._pairing_result is not None
        access_token, refresh_token, data = self._pairing_result
        await self.async_set_unique_id(data.user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=NAME,
            data={
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
                CONF_VERIFY_SSL: self._verify_ssl,
            },
        )

    async def async_step_authorization_denied(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when device authorization is denied."""
        return self.async_abort(reason="authorization_denied")

    async def async_step_authorization_expired(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when device authorization expires."""
        return self.async_abort(reason="authorization_expired")

    async def async_step_invalid_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when device authorization fails."""
        return self.async_abort(reason="invalid_auth")

    async def async_step_cannot_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when EvolvIOT cannot be reached."""
        return self.async_abort(reason="cannot_connect")

    async def async_step_unknown(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after an unexpected pairing error."""
        return self.async_abort(reason="unknown")

    def _pair_description_placeholders(self) -> dict[str, str]:
        """Return placeholders shown in the pairing form step."""
        return {
            "user_code": str(self._pairing.get("user_code") or ""),
            "expires_in": str(self._pairing.get("expires_in") or ""),
        }
