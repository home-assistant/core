"""Config flow to configure Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import denonavr
from denonavr.exceptions import AvrNetworkError, AvrTimoutError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .receiver import ConnectDenonAVR

_LOGGER = logging.getLogger(__name__)

DOMAIN = "denonavr"

SUPPORTED_MANUFACTURERS = ["Denon", "DENON", "DENON PROFESSIONAL", "Marantz"]
IGNORED_MODELS = ["HEOS 1", "HEOS 3", "HEOS 5", "HEOS 7"]

CONF_SHOW_ALL_SOURCES = "show_all_sources"
CONF_ZONE2 = "zone2"
CONF_ZONE3 = "zone3"
CONF_MODEL = "model"
CONF_MANUFACTURER = "manufacturer"
CONF_SERIAL_NUMBER = "serial_number"
CONF_UPDATE_AUDYSSEY = "update_audyssey"

DEFAULT_SHOW_SOURCES = False
DEFAULT_TIMEOUT = 5
DEFAULT_ZONE2 = False
DEFAULT_ZONE3 = False
DEFAULT_UPDATE_AUDYSSEY = False

CONFIG_SCHEMA = vol.Schema({vol.Optional(CONF_HOST): str})


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init object."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        settings_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_ALL_SOURCES,
                    default=self.config_entry.options.get(
                        CONF_SHOW_ALL_SOURCES, DEFAULT_SHOW_SOURCES
                    ),
                ): bool,
                vol.Optional(
                    CONF_ZONE2,
                    default=self.config_entry.options.get(CONF_ZONE2, DEFAULT_ZONE2),
                ): bool,
                vol.Optional(
                    CONF_ZONE3,
                    default=self.config_entry.options.get(CONF_ZONE3, DEFAULT_ZONE3),
                ): bool,
                vol.Optional(
                    CONF_UPDATE_AUDYSSEY,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=settings_schema)


class DenonAvrFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Denon AVR config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Denon AVR flow."""
        self.host = None
        self.serial_number = None
        self.model_name = None
        self.timeout = DEFAULT_TIMEOUT
        self.show_all_sources = DEFAULT_SHOW_SOURCES
        self.zone2 = DEFAULT_ZONE2
        self.zone3 = DEFAULT_ZONE3
        self.d_receivers = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # check if IP address is set manually
            host = user_input.get(CONF_HOST)
            if host:
                self.host = host
                return await self.async_step_connect()

            # discovery using denonavr library
            self.d_receivers = await denonavr.async_discover()
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

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return await self.async_step_connect()

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm")

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Connect to the receiver."""
        connect_denonavr = ConnectDenonAVR(
            self.host,
            self.timeout,
            self.show_all_sources,
            self.zone2,
            self.zone3,
            lambda: get_async_client(self.hass),
        )

        try:
            success = await connect_denonavr.async_connect_receiver()
        except (AvrNetworkError, AvrTimoutError):
            success = False
        if not success:
            return self.async_abort(reason="cannot_connect")
        receiver = connect_denonavr.receiver

        if not self.serial_number:
            self.serial_number = receiver.serial_number
        if not self.model_name:
            self.model_name = (receiver.model_name).replace("*", "")

        if self.serial_number is not None:
            unique_id = self.construct_unique_id(self.model_name, self.serial_number)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
        else:
            _LOGGER.error(
                "Could not get serial number of host %s, "
                "unique_id's will not be available",
                self.host,
            )
            for entry in self._async_current_entries():
                if entry.data[CONF_HOST] == self.host:
                    return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=receiver.name,
            data={
                CONF_HOST: self.host,
                CONF_TYPE: receiver.receiver_type,
                CONF_MODEL: self.model_name,
                CONF_MANUFACTURER: receiver.manufacturer,
                CONF_SERIAL_NUMBER: self.serial_number,
            },
        )

    async def async_step_ssdp(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle a discovered Denon AVR.

        This flow is triggered by the SSDP component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # Filter out non-Denon AVRs#1
        if (
            discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER)
            not in SUPPORTED_MANUFACTURERS
        ):
            return self.async_abort(reason="not_denonavr_manufacturer")

        # Check if required information is present to set the unique_id
        if (
            ssdp.ATTR_UPNP_MODEL_NAME not in discovery_info
            or ssdp.ATTR_UPNP_SERIAL not in discovery_info
        ):
            return self.async_abort(reason="not_denonavr_missing")

        self.model_name = discovery_info[ssdp.ATTR_UPNP_MODEL_NAME].replace("*", "")
        self.serial_number = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        self.host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname

        if self.model_name in IGNORED_MODELS:
            return self.async_abort(reason="not_denonavr_manufacturer")

        unique_id = self.construct_unique_id(self.model_name, self.serial_number)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured({CONF_HOST: self.host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, self.host)
                }
            }
        )

        return await self.async_step_confirm()

    @staticmethod
    def construct_unique_id(model_name: str, serial_number: str) -> str:
        """Construct the unique id from the ssdp discovery or user_step."""
        return f"{model_name}-{serial_number}"
