"""Config flow for go-e Charger integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult

import voluptuous as vol

from .const import DOMAIN
from .common import GoeChargerHub, CannotConnect, TimeoutOccured, InvalidRespStatus, InvalidJson, NotImplemented

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("secure", default=False): bool,
        vol.Required("host"): str,
        vol.Optional("pathprefix"): str,
        vol.Required("interval", default=5): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for go-e Charger."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        hub = GoeChargerHub(user_input["secure"], user_input["host"],
                            user_input["pathprefix"] if "pathprefix" in user_input else "")

        try:
            data = await hub.get_data(self.hass, ["sse"]);
        except CannotConnect:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA,
                                        errors={"base": "cannot_connect"})
        except TimeoutOccured:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA,
                                        errors={"base": "timeout_occured"})
        except InvalidRespStatus:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA,
                                        errors={"base": "invalid_resp_status"})
        except InvalidJson:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA,
                                        errors={"base": "invalid_json"})
        except NotImplemented:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA,
                                        errors={"base": "not_implemented"})
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception %s", str(e))
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={"base": "unknown"})

        # TODO duplicate search

        result = self.async_create_entry(title="go-e Charger " + data["sse"], data={
            "secure": user_input["secure"],
            "host": user_input["host"],
            "pathprefix": user_input["pathprefix"] if "pathprefix" in user_input else "",
            "serial": data["sse"],
        })

        return result


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        data_schema = vol.Schema(
            {
                vol.Required("secure", default=self._config_entry.data.get("secure")): bool,
                vol.Required("host", default=self._config_entry.data.get("host")): str,
                vol.Optional("pathprefix", default=self._config_entry.data.get("pathprefix")): str,
                vol.Required("interval", default=self._config_entry.data.get("interval")): int,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=data_schema)

        # return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=data_schema, errors={"base": "not_implemented"})
