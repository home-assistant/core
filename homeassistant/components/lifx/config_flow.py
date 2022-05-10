"""Config flow flow LIFX."""
from __future__ import annotations

import logging
from typing import Any

import aiolifx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_DISCOVERY_INTERVAL,
    CONF_DUPLICATE_DISCOVERY,
    CONF_GRACE_PERIOD,
    CONF_MESSAGE_TIMEOUT,
    CONF_RETRY_COUNT,
    DEFAULT_DISCOVERY_INTERVAL,
    DEFAULT_DUPLICATE_DISCOVERY,
    DEFAULT_GRACE_PERIOD,
    DEFAULT_MESSAGE_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class LifxConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a discovery config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the LIFX config flow."""
        self._domain = DOMAIN
        self._title = "LIFX"
        self._default_options = {
            CONF_DISCOVERY_INTERVAL: DEFAULT_DISCOVERY_INTERVAL,
            CONF_DUPLICATE_DISCOVERY: DEFAULT_DUPLICATE_DISCOVERY,
            CONF_GRACE_PERIOD: DEFAULT_GRACE_PERIOD,
            CONF_MESSAGE_TIMEOUT: DEFAULT_MESSAGE_TIMEOUT,
            CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
        }

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LifxOptionsFlowHandler(config_entry)

    async def _async_has_devices(self):
        """Return if there are devices that can be discovered."""
        lifx_ip_addresses = await aiolifx.LifxScan(self.hass.loop).scan()
        return len(lifx_ip_addresses) > 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain, raise_on_progress=False)

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(step_id="confirm")

        if self.source == config_entries.SOURCE_USER:
            # Get current discovered entries.
            in_progress = self._async_in_progress()

            if not (has_devices := in_progress):
                has_devices = await self._async_has_devices()

            if not has_devices:
                return self.async_abort(reason="no_devices_found")

            # Cancel the discovered one.
            for flow in in_progress:
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title=self._title, options=self._default_options)

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a flow initialized by discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by Homekit discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)
        return await self.async_step_confirm()


class LifxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the LIFX Options Flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the LIFX options flow."""
        self.config_entry = config_entry
        self.updated_config: dict[str, Any] = {}

    async def async_step_init(self, user_input=None):
        """Handle configuration initiated by a user."""
        return await self.async_step_discovery_options(user_input)

    async def async_step_discovery_options(self, user_input=None):
        """Handle custom discovery option dialog and store."""
        errors = {}
        current_options = self.config_entry.options

        if user_input is not None:
            self.updated_options = dict(current_options)
            self.updated_options[CONF_DISCOVERY_INTERVAL] = user_input.get(
                CONF_DISCOVERY_INTERVAL
            )
            self.updated_options[CONF_DUPLICATE_DISCOVERY] = user_input.get(
                CONF_DUPLICATE_DISCOVERY
            )
            self.updated_options[CONF_MESSAGE_TIMEOUT] = user_input.get(
                CONF_MESSAGE_TIMEOUT
            )
            self.updated_options[CONF_RETRY_COUNT] = user_input.get(CONF_RETRY_COUNT)
            self.updated_options[CONF_GRACE_PERIOD] = user_input.get(CONF_GRACE_PERIOD)
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=self.updated_options
            )

            reloaded = await self.hass.services.async_call(
                "homeassistant",
                "reload_config_entry",
                service_data={"entry_id": self.config_entry.entry_id},
                blocking=True,
                limit=30,
            )
            title = (
                "LIFX integration reloaded successfully."
                if reloaded
                else "LIFX integration could not be reloaded. Please restart Home Assistant."
            )

            return self.async_create_entry(title=title, data=None)

        options_schema = {
            vol.Required(
                CONF_DISCOVERY_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_DISCOVERY_INTERVAL, DEFAULT_DISCOVERY_INTERVAL
                ),
            ): cv.positive_int,
            vol.Required(
                CONF_DUPLICATE_DISCOVERY,
                default=self.config_entry.options.get(
                    CONF_DUPLICATE_DISCOVERY, DEFAULT_DUPLICATE_DISCOVERY
                ),
            ): cv.boolean,
            vol.Required(
                CONF_MESSAGE_TIMEOUT,
                default=self.config_entry.options.get(
                    CONF_MESSAGE_TIMEOUT, DEFAULT_MESSAGE_TIMEOUT
                ),
            ): cv.positive_float,
            vol.Required(
                CONF_RETRY_COUNT,
                default=self.config_entry.options.get(
                    CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                ),
            ): cv.positive_int,
            vol.Required(
                CONF_GRACE_PERIOD,
                default=self.config_entry.options.get(
                    CONF_GRACE_PERIOD, DEFAULT_GRACE_PERIOD
                ),
            ): cv.positive_int,
        }

        return self.async_show_form(
            step_id="discovery_options",
            data_schema=vol.Schema(options_schema),
            errors=errors,
            last_step=True,
        )
