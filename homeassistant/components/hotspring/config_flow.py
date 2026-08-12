"""Config flow for Hot Spring."""

from typing import override

from hotspring import HotSpring, HotSpringConnectionError, HotSpringError, Spa
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> Spa:
    """Validate the user input allows us to connect."""
    api = HotSpring(data[CONF_HOST], session=async_get_clientsession(hass))
    spa = await api.update()
    if not spa.info.mac_address:
        raise HotSpringError("No MAC address found")
    return spa


class HotSpringConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hot Spring."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                spa = await validate_input(self.hass, user_input)
            except HotSpringConnectionError, HotSpringError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(spa.info.mac_address)
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
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
