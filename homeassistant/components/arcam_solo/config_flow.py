"""Config flow for the Arcam Solo integration."""

import logging
from typing import Any

from pyarcamsolo import ArcamSolo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(
            selector.TextSelectorConfig(autocomplete="off")
        ),
        vol.Required(CONF_DEVICE): selector.SerialPortSelector(),
    }
)


class ArcamSoloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Arcam Solo."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            try:
                solo = ArcamSolo(uri=user_input[CONF_DEVICE])
                await solo.connect(
                    reconnect=False
                )  # don't auto-reconnect if the connection is lost
            except TimeoutError, OSError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await solo.disconnect()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
