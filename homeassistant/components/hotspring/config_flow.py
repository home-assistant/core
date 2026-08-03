"""Config flow for Hot Spring."""

from typing import Any, override

from hotspring import HotSpring, HotSpringConnectionError, HotSpringError, Spa
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class HotSpringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hot Spring."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                spa = await self._async_get_spa(user_input[CONF_HOST])
            except HotSpringConnectionError, HotSpringError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    spa.info.mac_address or spa.info.root_topic
                )
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=spa.info.hostname or "Hot Spring Spa",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def _async_get_spa(self, host: str) -> Spa:
        """Get information from a Hot Spring spa."""
        api = HotSpring(host, session=async_get_clientsession(self.hass))
        return await api.update()
