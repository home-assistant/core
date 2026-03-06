"""Config flow for the Denon RS232 integration."""

from __future__ import annotations

import logging
from typing import Any

from denon_rs232 import DenonReceiver
from denon_rs232.models import MODELS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT

from .const import CONF_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)

MODEL_OPTIONS = {key: model.name for key, model in MODELS.items()}

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL): vol.In(MODEL_OPTIONS),
        vol.Required(CONF_PORT): str,
    }
)


class DenonRS232ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Denon RS232."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_PORT: user_input[CONF_PORT]})

            model = MODELS[user_input[CONF_MODEL]]
            receiver = DenonReceiver(user_input[CONF_PORT], model=model)
            try:
                await receiver.connect()
            except ConnectionError, OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await receiver.disconnect()
                return self.async_create_entry(
                    title=f"Denon {model.name} ({user_input[CONF_PORT]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )
