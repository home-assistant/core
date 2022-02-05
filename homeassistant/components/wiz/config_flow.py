"""Config flow for WiZ Platform."""
from __future__ import annotations

import logging
from typing import Any

from pywizlight import wizlight
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN
from .utils import _short_mac

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            bulb = wizlight(user_input[CONF_HOST])
            try:
                mac = await bulb.getMac()
                bulbtype = await bulb.get_bulbtype()
            except WizLightTimeOutError:
                errors["base"] = "bulb_time_out"
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except WizLightConnectionError:
                errors["base"] = "no_wiz_light"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                bulb_type = bulbtype.bulb_type.value if bulbtype else "Unknown"
                name = f"{DEFAULT_NAME} {bulb_type} {_short_mac(mac)}"
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
