"""Config flow for Palazzetti."""

from typing import Any

from palazzetti_sdk_local_api import Hub
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr

from .const import API_MAC, API_NAME, DOMAIN, HOST, MAC, NAME, PALAZZETTI


class PalazzettiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Palazzetti config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User confiiguration step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str})
            )

        host = user_input[CONF_HOST]
        hub = Hub(host=host, isbiocc=False)
        await hub.async_update(discovery=False, deep=False)

        attributes = hub.get_attributes()

        if API_MAC not in attributes:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                errors={"base": "invalid_host"},
            )
        formatted_mac = dr.format_mac(attributes[API_MAC])
        device_unique_id = formatted_mac

        # Assign a unique ID to the flow
        await self.async_set_unique_id(device_unique_id)

        # Abort the flow if a config entry with the same unique ID exists
        self._abort_if_unique_id_configured()

        name = attributes.get(API_NAME, PALAZZETTI)
        return self.async_create_entry(
            title=name,
            data={NAME: name, HOST: host, MAC: formatted_mac},
        )
