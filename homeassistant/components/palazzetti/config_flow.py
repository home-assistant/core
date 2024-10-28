"""Config flow for Palazzetti."""

from typing import Any

from pypalazzetti.client import PalazzettiClient
from pypalazzetti.exceptions import CommunicationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER


class PalazzettiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Palazzetti config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            client = PalazzettiClient(hostname=host)
            try:
                await client.connect()
            except CommunicationError:
                LOGGER.exception("Communication error")
                errors["base"] = "cannot_connect"
            else:
                formatted_mac = dr.format_mac(client.mac)

                # Assign a unique ID to the flow
                await self.async_set_unique_id(formatted_mac)

                # Abort the flow if a config entry with the same unique ID exists
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=client.name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
