"""Config flow for SimpleFIN integration."""

from typing import Any

from simplefin4py import SimpleFin
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

CREDS_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the initial setup of a SimpleFIN integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt user for SimpleFIN API credentials."""
        return await self._show_creds_form()

    async def async_step_creds(self, user_input: dict[str, Any]) -> FlowResult:
        """Create config entry."""
        access_url = await SimpleFin.claim_setup_token(user_input[CONF_API_TOKEN])

        return self.async_create_entry(
            title="SimpleFIN", data={"access_url": access_url}
        )

    async def _show_creds_form(self) -> FlowResult:
        return self.async_show_form(
            step_id="creds", data_schema=CREDS_FORM_SCHEMA, last_step=False
        )
