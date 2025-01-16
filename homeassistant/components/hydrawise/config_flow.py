"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from aiohttp import ClientError
from pydrawise import auth as pydrawise_auth, client
from pydrawise.exceptions import NotAuthorizedError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import APP_ID, DOMAIN, LOGGER


class HydrawiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1

    async def _create_or_update_entry(
        self,
        username: str,
        password: str,
        *,
        on_failure: Callable[[str], ConfigFlowResult],
    ) -> ConfigFlowResult:
        """Create the config entry."""
        # Verify that the provided credentials work."""
        auth = pydrawise_auth.Auth(username, password)
        try:
            await auth.token()
        except NotAuthorizedError:
            return on_failure("invalid_auth")
        except TimeoutError:
            return on_failure("timeout_connect")

        try:
            api = client.Hydrawise(auth, app_id=APP_ID)
            # Don't fetch zones because we don't need them yet.
            user = await api.get_user(fetch_zones=False)
        except TimeoutError:
            return on_failure("timeout_connect")
        except ClientError as ex:
            LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
            return on_failure("cannot_connect")

        await self.async_set_unique_id(f"hydrawise-{user.customer_id}")

        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Hydrawise",
                data={CONF_USERNAME: username, CONF_PASSWORD: password},
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_USERNAME: username, CONF_PASSWORD: password},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup."""
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            return await self._create_or_update_entry(
                username=username, password=password, on_failure=self._show_form
            )
        return self._show_form()

    def _show_form(self, error_type: str | None = None) -> ConfigFlowResult:
        errors = {}
        if error_type is not None:
            errors["base"] = error_type
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth after updating config to username/password."""
        return await self.async_step_user()
