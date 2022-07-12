"""Config flow for iNels."""
from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, INELS_VERSION, MANUAL_SETUP

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="core-mosquitto"): str,
        vol.Required(CONF_PORT, default=1883): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class InelsFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle of Inels config flow."""

    VERSION = INELS_VERSION

    def __init__(self) -> None:
        """Initialize the Inels flow."""
        self.mqtt: InelsMqtt | None = None
        self.discovered_brokers: dict[str, InelsMqtt] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle flow initialized by the user."""
        return await self.async_step_user(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle flow start."""
        # check if manual entry was chosen
        if user_input is not None and user_input[CONF_ID] == MANUAL_SETUP:
            return await self.async_step_manual()

        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual mqtt broker setup."""
        if user_input is None:
            # set the form inputs
            return self.async_show_form(
                step_id="manual", data_schema=STEP_MANUAL_DATA_SCHEMA
            )

        await self.async_set_unique_id("abcddddd")
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Attepmt to link with the mqtt broker."""

        if user_input is None:
            return self.async_show_form(step_id="link")

        return self.async_create_entry(title="iNELS", data=user_input)

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle discover mqtt broker."""
        if discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER) not in ("ddd", "aaa"):
            return self.async_abort(reason="not_mqtt_broker")

        await self.async_set_unique_id("abcddddd")

        return await self.async_step_link()
