"""Config flow for Radio Browser integration."""

from typing import Any, override

from radios import RadioBrowser, RadioBrowserError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import __version__
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class RadioBrowserConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Browser."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            radios = RadioBrowser(
                session=async_get_clientsession(self.hass),
                user_agent=f"HomeAssistant/{__version__}",
            )
            try:
                await radios.stats()
            except RadioBrowserError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Radio Browser", data={})

        return self.async_show_form(step_id="user", errors=errors)

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(title="Radio Browser", data={})
