"""Authentication provider to authenticate using Synology DSM."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.auth import AuthProvider
from homeassistant.auth.models import Credentials, UserMeta
from homeassistant.auth.providers import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, LoginFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

CONFIG_SCHEMA = AUTH_PROVIDER_SCHEMA.extend(
    {
        vol.Required("host"): str,
        vol.Required("port"): int,
        vol.Required("secure", default=False): bool,
        vol.Optional("verify_cert", default=False): bool,
    }
)

_LOGGER = logging.getLogger(__name__)


class SynologyAuthenticationError(HomeAssistantError):
    """Error to indicate an error while authenticating to Synology DSM."""


class SynologyConnectionError(SynologyAuthenticationError):
    """Error to indicate an error with the connection to Synology DSM."""


class SynologyLoginError(SynologyAuthenticationError):
    """Error to indicate invalid credentials while logging in to Synology DSM.."""


class Synology2FAError(SynologyLoginError):
    """Error to indicate invalid or missing 2FA while logging in to Synology DSM.."""


@AUTH_PROVIDERS.register("synology")
class SynologyAuthProvider(AuthProvider):
    """Auth provider for Synology DSM.

    Based on https://global.download.synology.com/download/Document/Software/DeveloperGuide/Os/DSM/All/enu/DSM_Login_Web_API_Guide_enu.pdf
    """

    DEFAULT_TITLE = "Synology DSM authentication"

    @property
    def _api_url(self) -> str:
        """Return the API URL for the configured Synology DSM."""
        protocol = "http"
        if self.config["secure"]:
            protocol = "https"
        return (
            f"{protocol}://{self.config['host']}:{self.config['port']}/webapi/entry.cgi"
        )

    async def async_login_flow(self, context: dict[str, Any] | None) -> LoginFlow:
        """Provide Synology login flow."""
        return SynologyLoginFlow(self)

    async def async_validate_login(
        self, username: str, password: str, otp_code: str
    ) -> dict[str, Any]:
        """Validate credentials with Synology DSM."""
        session = async_get_clientsession(self.hass, self.config["verify_cert"])

        try:
            query_params = {
                "api": "SYNO.API.Auth",
                "version": 7,
                "method": "login",
                "format": "sid",
                "account": username,
                "passwd": password,
            }
            if otp_code != "":
                query_params["otp_code"] = otp_code

            login_response = await session.get(self._api_url, params=query_params)
        except Exception as ex:
            _LOGGER.error("Error connecting to Synology DSM: %s", ex)
            raise SynologyConnectionError(ex) from ex

        if login_response.status != 200:
            _LOGGER.error(
                "Status code %s in authentication response not successful",
                login_response.status,
            )
            raise SynologyConnectionError(
                f"Connection to Synology DSM did not succeed. Status code: {login_response.status}"
            )

        login_response_json = await login_response.json()
        if not login_response_json["success"]:
            _LOGGER.warning(
                "Authentication failed with Synology error code %s",
                login_response_json["error"]["code"],
            )
            if login_response_json["error"]["code"] < 400:
                raise SynologyConnectionError(
                    f"Connection to Synology DSM did not succeed. Synology error code: {login_response_json['error']['code']}"
                )
            if login_response_json["error"]["code"] in [403, 404, 406]:
                raise Synology2FAError(
                    f"2-factor authentication failed with code {login_response_json['error']['code']}"
                )
            raise SynologyLoginError(
                f"Authentication failed with code {login_response_json['error']['code']}"
            )
        _LOGGER.info(
            "User %s successfully authenticated to Synology DSM",
            login_response_json["data"]["account"],
        )
        return {
            k: login_response_json["data"][k]
            for k in login_response_json["data"].keys()
        }

    async def async_get_or_create_credentials(
        self, flow_result: Mapping[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        account = flow_result["account"]

        for credential in await self.async_credentials():
            if credential.data["account"] == account:
                return credential

        # Create new credentials.
        credential_data = {k: flow_result[k] for k in flow_result.keys()}
        credential_data.update({"username": account})
        return self.async_create_credentials(credential_data)

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Provide user metadata for new users."""

        session = async_get_clientsession(self.hass, self.config["verify_cert"])
        query_params = {
            "api": "SYNO.Core.NormalUser",
            "version": 1,
            "method": "get",
            "_sid": credentials.data["sid"],
        }
        try:
            apis_response = await session.get(self._api_url, params=query_params)
            apis_response_json = await apis_response.json()
            full_name = apis_response_json["data"]["fullname"]
            username = apis_response_json["data"]["username"]
            # email is available as well, but not used at the moment
            return UserMeta(
                full_name if full_name != "" else username,
                True,
            )
        except Exception as ex:
            _LOGGER.error("Error while retrieving user info: %s", ex)
            raise SynologyAuthenticationError(ex) from ex


class SynologyLoginFlow(LoginFlow):
    """Login flow for Synology DSM."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the corresponding UI."""
        errors = {}

        if user_input is not None:
            username = (
                user_input["username"].strip()
                if user_input.get("username") is not None
                else ""
            )
            if username == "":
                errors["username"] = "empty_username"

            password = (
                user_input["password"].strip()
                if user_input.get("password") is not None
                else ""
            )
            if password == "":
                errors["password"] = "empty_password"

            otp_code = (
                user_input["otp_code"].strip()
                if user_input.get("otp_code") is not None
                else ""
            )

            if len(errors) == 0:
                try:
                    data = await cast(
                        SynologyAuthProvider, self._auth_provider
                    ).async_validate_login(username, password, otp_code)
                    return await self.async_finish(data)
                except Synology2FAError:
                    errors["otp_code"] = "otp_required"
                except SynologyLoginError:
                    errors["base"] = "invalid_auth"
                except SynologyAuthenticationError:
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Optional("otp_code"): str,
                }
            ),
            errors=errors,
        )
