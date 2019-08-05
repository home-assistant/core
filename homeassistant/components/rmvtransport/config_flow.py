"""Config flow to configure the Rhein-Main public transport component."""
from collections import OrderedDict
import hashlib

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_SHOW_ON_MAP
from homeassistant.helpers import aiohttp_client

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_HASH,
    CONF_STATION,
    CONF_DESTINATIONS,
    CONF_DIRECTION,
    CONF_LINES,
    CONF_PRODUCTS,
    CONF_TIME_OFFSET,
    CONF_MAX_JOURNEYS,
    VALID_PRODUCTS,
)


@config_entries.HANDLERS.register(DOMAIN)
class RMVTransportFlowHandler(config_entries.ConfigFlow):
    """Handle a rmv transport config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the RMV transport config flow."""
        self.rmv_config = {}

    async def _show_form_lines(self, errors=None):
        """Show the setup form to the user."""
        data_schema = OrderedDict()
        data_schema[vol.Optional(CONF_DESTINATIONS)] = str
        data_schema[vol.Optional(CONF_LINES, default="")] = str
        data_schema[vol.Optional(CONF_DIRECTION)] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )

    async def _show_form_products(self, errors=None):
        """Show the setup form to the user."""
        data_schema = OrderedDict()

        for product in VALID_PRODUCTS:
            data_schema[vol.Optional(product, default=True)] = bool

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )

    async def _show_form_details(self, errors=None):
        """Show the form to the user."""
        data_schema = OrderedDict()
        data_schema[vol.Optional(CONF_NAME, default=self.rmv_config[CONF_NAME])] = str
        data_schema[vol.Optional(CONF_SHOW_ON_MAP, default=False)] = bool
        data_schema[vol.Optional(CONF_TIME_OFFSET, default=0)] = int
        data_schema[vol.Optional(CONF_MAX_JOURNEYS, default=5)] = int
        data_schema[
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL.seconds)
        ] = int

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )

    async def _show_form_station(self, errors=None):
        """Show the form to the user."""
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_STATION)] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {}
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from RMVtransport import RMVtransport
        from RMVtransport.rmvtransport import (
            RMVtransportApiConnectionError,
            RMVtransportError,
        )

        if user_input is not None:
            self.rmv_config.update(user_input)

        if self.rmv_config.get(CONF_STATION) is None:
            return await self._show_form_station()

        session = aiohttp_client.async_get_clientsession(self.hass)
        rmv = RMVtransport(session)

        if self.rmv_config.get(CONF_NAME) is None:
            try:
                data = await rmv.get_departures(self.rmv_config[CONF_STATION])
                self.rmv_config[CONF_NAME] = str(data["station"])
            except RMVtransportApiConnectionError:
                return self._show_form_station({CONF_STATION: "communication_error"})
            except RMVtransportError:
                return self._show_form_station({CONF_STATION: "invalid_sensor"})

        if (
            self.rmv_config.get("Bus") is None
            and self.rmv_config.get(CONF_PRODUCTS) is None
        ):
            return await self._show_form_products()
        if self.rmv_config.get(CONF_PRODUCTS) is None:
            self.rmv_config[CONF_PRODUCTS] = []
            for product in VALID_PRODUCTS:
                if user_input[product] is True:
                    self.rmv_config[CONF_PRODUCTS].append(product)
                del self.rmv_config[product]

        if self.rmv_config.get(CONF_SHOW_ON_MAP) is None:
            return await self._show_form_details()

        if self.rmv_config.get(CONF_LINES) is None:
            return await self._show_form_lines()
        if isinstance(self.rmv_config.get(CONF_LINES), str):
            if self.rmv_config[CONF_LINES] == "":
                self.rmv_config[CONF_LINES] = []
            else:
                self.rmv_config[CONF_LINES] = [
                    x.strip() for x in self.rmv_config[CONF_LINES].split(",")
                ]

        user_input_hash = hashlib.sha224(f"{self.rmv_config}".encode()).hexdigest()
        self.rmv_config[CONF_HASH] = user_input_hash

        existing_entities = set(
            entry.data[CONF_HASH]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )
        if user_input_hash in existing_entities:
            return await self._show_form_station({CONF_STATION: "sensor_exists"})

        return self.async_create_entry(
            title=self.rmv_config[CONF_NAME], data=self.rmv_config
        )
