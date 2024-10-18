"""Config flow for Palazzetti."""

from typing import Any

from pypalazzetti.client import PalazzettiClient
from pypalazzetti.exceptions import CommunicationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, LOGGER


class PalazzettiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Palazzetti config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User configuration step."""
        if user_input and CONF_HOST in user_input:
            host = user_input[CONF_HOST]
            palazzetti = PalazzettiClient(hostname=host)
            try:
                success = await palazzetti.connect()
            except CommunicationError:
                LOGGER.exception("Communication error")
                success = False

            if not success:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                    errors={"base": "invalid_host"},
                )

            formatted_mac = dr.format_mac(palazzetti.mac)

            # Assign a unique ID to the flow
            await self.async_set_unique_id(formatted_mac)

            # Abort the flow if a config entry with the same unique ID exists
            self._abort_if_unique_id_configured()

            name = palazzetti.name
            return self.async_create_entry(
                title=name,
                data={CONF_NAME: name, CONF_HOST: host, CONF_MAC: formatted_mac},
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str})
        )
