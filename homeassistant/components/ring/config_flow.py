"""Config flow for Ring integration."""
from collections.abc import Mapping
import logging
from typing import Any

from ring_doorbell import Auth, AuthenticationError, Requires2FAError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, __version__ as ha_version
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    auth = Auth(f"HomeAssistant/{ha_version}")

    token = await hass.async_add_executor_job(
        auth.fetch_token,
        data["username"],
        data["password"],
        data.get("2fa"),
    )

    return token


class RingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 2

    user_pass: dict[str, Any] = {}

    reauth_entry: ConfigEntry | None = None

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def _async_create_or_update_entry(
        self,
        *,
        title: str,
        data: Mapping[str, Any],
    ) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.reauth_entry:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return super().async_create_entry(title=title, data=data)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                token = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input["username"])

                return await self._async_create_or_update_entry(
                    title=user_input["username"],
                    data={"username": user_input["username"], CONF_ACCESS_TOKEN: token},
                )
            except Requires2FAError:
                self.user_pass = user_input
                return await self.async_step_2fa()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("username"): str, vol.Required("password"): str}
            ),
            errors=errors,
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        if user_input:
            return await self.async_step_user({**self.user_pass, **user_input})

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema({vol.Required("2fa"): str}),
        )
