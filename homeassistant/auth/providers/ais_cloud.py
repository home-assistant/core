"""Example auth provider."""
from collections import OrderedDict
import hmac
from typing import Any, Dict, Optional, cast

import voluptuous as vol

from homeassistant.components.ais_dom import ais_global
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from . import AUTH_PROVIDER_SCHEMA, AUTH_PROVIDERS, AuthProvider, LoginFlow
from ..models import Credentials, UserMeta

CONFIG_SCHEMA = vol.All(AUTH_PROVIDER_SCHEMA)


class InvalidAuthError(HomeAssistantError):
    """Raised when submitting invalid authentication."""


@AUTH_PROVIDERS.register("ais_cloud")
class AisCloudAuthProvider(AuthProvider):
    """Auth provider based on AIS Portal."""

    DEFAULT_TITLE = "AIS Portal"

    async def async_login_flow(self, context: Optional[Dict]) -> LoginFlow:
        """Return a flow to login."""
        return AisLoginFlow(self)

    @callback
    def async_validate_login(self, username: str, password: str, gate_id: str) -> None:
        """Validate a username and password."""
        user = None

        # Get user info from AIS
        if gate_id is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password.encode("utf-8"), password.encode("utf-8"))
            raise InvalidAuthError

        if user is None:
            # Do one more compare to make timing the same as if user was found.
            hmac.compare_digest(password.encode("utf-8"), password.encode("utf-8"))
            raise InvalidAuthError

        if not hmac.compare_digest(
            user["password"].encode("utf-8"), password.encode("utf-8")
        ):
            raise InvalidAuthError

    async def async_get_or_create_credentials(
        self, flow_result: Dict[str, str]
    ) -> Credentials:
        """Get credentials based on the flow result."""
        username = flow_result["username"]

        for credential in await self.async_credentials():
            if credential.data["username"] == username:
                return credential

        # Create new credentials.
        return self.async_create_credentials({"username": username})

    async def async_user_meta_for_credentials(
        self, credentials: Credentials
    ) -> UserMeta:
        """Return extra user metadata for credentials.

        Will be used to populate info when creating a new user.
        """
        username = credentials.data["username"]
        name = None

        for user in self.config["users"]:
            if user["username"] == username:
                name = user.get("name")
                break

        return UserMeta(name=name, is_active=True)


class AisLoginFlow(LoginFlow):
    """Handler for the login flow."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle the step of the form."""
        errors = {}

        if user_input is not None:
            try:
                cast(AisCloudAuthProvider, self._auth_provider).async_validate_login(
                    user_input["username"],
                    user_input["password"],
                    user_input["gate_id"],
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"

            if not errors:
                user_input.pop("password")
                return await self.async_finish(user_input)

        sercure_android_id_dom = ais_global.get_sercure_android_id_dom()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("gate_id"): vol.In([sercure_android_id_dom]),
                }
            ),
            errors=errors,
        )
