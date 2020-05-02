"""Config flow to configure Denon AVR receivers using their HTTP interface."""
import logging

import denonavr
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TIMEOUT

from .receiver import ConnectDenonAVR

_LOGGER = logging.getLogger(__name__)

DOMAIN = "denonavr"

CONF_SHOW_ALL_SOURCES = "show_all_sources"
CONF_ZONE2 = "zone2"
CONF_ZONE3 = "zone3"

DEFAULT_SHOW_SOURCES = False
DEFAULT_TIMEOUT = 2

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): str,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            int, vol.Range(min=1)
        ),
        vol.Optional(CONF_SHOW_ALL_SOURCES, default=DEFAULT_SHOW_SOURCES): bool,
        vol.Optional(CONF_ZONE2, default=False): bool,
        vol.Optional(CONF_ZONE3, default=False): bool,
    }
)


class DenonAvrFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Denon AVR config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Denon AVR flow."""
        self.host = None
        self.timeout = DEFAULT_TIMEOUT
        self.show_all_sources = DEFAULT_SHOW_SOURCES
        self.zone2 = False
        self.zone3 = False
        self.d_receivers = []

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Get config option that have defaults
            self.timeout = user_input[CONF_TIMEOUT]
            self.show_all_sources = user_input[CONF_SHOW_ALL_SOURCES]
            self.zone2 = user_input[CONF_ZONE2]
            self.zone3 = user_input[CONF_ZONE3]

            # check if IP adress is set manually
            host = user_input.get(CONF_HOST)
            if host:
                self.host = host
                return await self.async_step_connect()

            # discovery using denonavr library
            self.d_receivers = await self.hass.async_add_executor_job(denonavr.discover)
            # More than one receiver could be discovered by that method
            if len(self.d_receivers) == 1:
                self.host = self.d_receivers[0]["host"]
                return await self.async_step_connect()
            if len(self.d_receivers) > 1:
                # show selection form
                return await self.async_step_select()

            errors["base"] = "discovery_error"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_select(self, user_input=None):
        """Handle multiple receivers found."""
        errors = {}
        if user_input is not None:
            self.host = user_input["select_host"]
            return await self.async_step_connect()

        select_scheme = vol.Schema(
            {
                vol.Required("select_host"): vol.In(
                    [d_receiver["host"] for d_receiver in self.d_receivers]
                )
            }
        )

        return self.async_show_form(
            step_id="select", data_schema=select_scheme, errors=errors
        )

    async def async_step_connect(self, user_input=None):
        """Connect to the receiver."""
        connect_denonavr = ConnectDenonAVR(self.hass, self.host, self.timeout, self.show_all_sources, self.zone2, self.zone3)
        if not await connect_denonavr.async_connect_receiver():
            return self.async_abort(reason="connection_error")
        receiver = connect_denonavr.receiver

        unique_id = f"{receiver.model_name}-{receiver.serial_number}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=receiver.name,
            data={
                CONF_HOST: self.host,
                CONF_TIMEOUT: self.timeout,
                CONF_SHOW_ALL_SOURCES: self.show_all_sources,
                CONF_ZONE2: self.zone2,
                CONF_ZONE3: self.zone3,
                "receiver_id": unique_id,
            },
        )
