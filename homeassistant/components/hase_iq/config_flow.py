"""Config flow for the Hase iQ integration."""

from typing import Any, override

import probatio
from pyhaseiq import Client, HaseIQError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import TextSelector

from .const import DOMAIN, LOGGER

STEP_USER_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): TextSelector()})


class HaseIQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hase iQ."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a stove configured by its address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # The stove exposes no serial number or MAC address to use as unique id.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                async with Client(user_input[CONF_HOST]) as stove:
                    await stove.get_phase()
            except HaseIQError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Hase iQ", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )
