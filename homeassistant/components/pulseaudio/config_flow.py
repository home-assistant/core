"""Config flow for PulseAudio integration."""
from __future__ import annotations

import logging

from pulsectl import Pulse, PulseError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import CONF_MEDIAPLAYER_SINKS, CONF_MEDIAPLAYER_SOURCES, CONF_SERVER
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_SERVER, default="localhost:4713"): str}
)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


def _verify_server(server: str) -> tuple[bool, set | None, set | None]:
    """Verify PulseAudio connection."""
    try:
        pulse = Pulse(server=server)
        if pulse.connected:
            return (True, pulse.sink_list(), pulse.source_list())

    except PulseError:
        pass

    return (False, None, None)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    result, sinks, sources = await hass.async_add_executor_job(
        _verify_server, data["server"]
    )

    if not result:
        raise CannotConnect

    return {"sinks": sinks, "sources": sources}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PulseAudio."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    server = ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        for entry in self._async_current_entries():
            if entry.data[CONF_SERVER] == user_input["server"]:
                return self.async_abort(reason="already_configured")

        try:
            await validate_input(self.hass, user_input)
            self.server = user_input["server"]
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(title=self.server, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for PulseAudio."""

    server = ""
    sinks: set[str] = set()
    sources: set[str] = set()

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize PulseAudio options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        errors = {}

        sink_names = []
        source_names = []

        try:
            info = await validate_input(self.hass, self.config_entry.data)
            self.server = self.config_entry.options.get("server")
            self.sinks = info["sinks"]
            self.sources = info["sources"]

            for sink in self.sinks:
                sink_names.append(sink.name)

            for source in self.sources:
                source_names.append(source.name)

        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MEDIAPLAYER_SINKS,
                        default=self.config_entry.options.get(CONF_MEDIAPLAYER_SINKS),
                    ): cv.multi_select(sink_names),
                    vol.Required(
                        CONF_MEDIAPLAYER_SOURCES,
                        default=self.config_entry.options.get(CONF_MEDIAPLAYER_SOURCES),
                    ): cv.multi_select(source_names),
                }
            ),
            errors=errors,
        )
