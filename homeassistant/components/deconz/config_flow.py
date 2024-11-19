"""Config flow to configure deCONZ component."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from pprint import pformat
from typing import Any, cast
from urllib.parse import urlparse

from pydeconz.errors import LinkButtonNotPressed, RequestError, ResponseError
from pydeconz.gateway import DeconzSession
from pydeconz.utils import (
    DiscoveredBridge,
    discovery as deconz_discovery,
    get_bridge_id as deconz_get_bridge_id,
    normalize_bridge_id,
)
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    SOURCE_HASSIO,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_ALLOW_NEW_DEVICES,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_ALLOW_NEW_DEVICES,
    DEFAULT_PORT,
    DOMAIN,
    HASSIO_CONFIGURATION_URL,
    LOGGER,
)
from .hub import DeconzHub

DECONZ_MANUFACTURERURL = "http://www.dresden-elektronik.de"
CONF_SERIAL = "serial"
CONF_MANUAL_INPUT = "Manually define gateway"


@callback
def get_master_hub(hass: HomeAssistant) -> DeconzHub:
    """Return the gateway which is marked as master."""
    for hub in hass.data[DOMAIN].values():
        if hub.master:
            return cast(DeconzHub, hub)
    raise ValueError


class DeconzFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a deCONZ config flow."""

    VERSION = 1

    _hassio_discovery: dict[str, Any]

    bridges: list[DiscoveredBridge]
    host: str
    port: int
    api_key: str

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DeconzOptionsFlowHandler:
        """Get the options flow for this handler."""
        return DeconzOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the deCONZ config flow."""
        self.bridge_id = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a deCONZ config flow start.

        Let user choose between discovered bridges and manual configuration.
        If no bridge is found allow user to manually input configuration.
        """
        if user_input is not None:
            if user_input[CONF_HOST] == CONF_MANUAL_INPUT:
                return await self.async_step_manual_input()

            for bridge in self.bridges:
                if bridge[CONF_HOST] == user_input[CONF_HOST]:
                    self.bridge_id = bridge["id"]
                    self.host = bridge[CONF_HOST]
                    self.port = bridge[CONF_PORT]
                    return await self.async_step_link()

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(10):
                self.bridges = await deconz_discovery(session)

        except (TimeoutError, ResponseError):
            self.bridges = []

        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug("Discovered deCONZ gateways %s", pformat(self.bridges))

        if self.bridges:
            hosts = [bridge[CONF_HOST] for bridge in self.bridges]

            hosts.append(CONF_MANUAL_INPUT)

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Optional(CONF_HOST): vol.In(hosts)}),
            )

        return await self.async_step_manual_input()

    async def async_step_manual_input(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual configuration."""
        if user_input:
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]
            return await self.async_step_link()

        return self.async_show_form(
            step_id="manual_input",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the deCONZ bridge."""
        errors: dict[str, str] = {}

        LOGGER.debug(
            "Preparing linking with deCONZ gateway %s %d", self.host, self.port
        )

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            deconz_session = DeconzSession(session, self.host, self.port)

            try:
                async with asyncio.timeout(10):
                    api_key = await deconz_session.get_api_key()

            except LinkButtonNotPressed:
                errors["base"] = "linking_not_possible"

            except (ResponseError, RequestError, TimeoutError):
                errors["base"] = "no_key"

            else:
                self.api_key = api_key
                return await self._create_entry()

        return self.async_show_form(step_id="link", errors=errors)

    async def _create_entry(self) -> ConfigFlowResult:
        """Create entry for gateway."""
        if not self.bridge_id:
            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                async with asyncio.timeout(10):
                    self.bridge_id = await deconz_get_bridge_id(
                        session, self.host, self.port, self.api_key
                    )
                    await self.async_set_unique_id(self.bridge_id)

                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: self.host,
                            CONF_PORT: self.port,
                            CONF_API_KEY: self.api_key,
                        }
                    )

            except TimeoutError:
                return self.async_abort(reason="no_bridges")

        return self.async_create_entry(
            title=self.bridge_id,
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_API_KEY: self.api_key,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        self.context["title_placeholders"] = {CONF_HOST: entry_data[CONF_HOST]}

        self.host = entry_data[CONF_HOST]
        self.port = entry_data[CONF_PORT]

        return await self.async_step_link()

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered deCONZ bridge."""
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug("deCONZ SSDP discovery %s", pformat(discovery_info))

        self.bridge_id = normalize_bridge_id(discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL])
        parsed_url = urlparse(discovery_info.ssdp_location)

        entry = await self.async_set_unique_id(self.bridge_id)
        if entry and entry.source == SOURCE_HASSIO:
            return self.async_abort(reason="already_configured")

        self.host = cast(str, parsed_url.hostname)
        self.port = cast(int, parsed_url.port)

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
            }
        )

        self.context.update(
            {
                "title_placeholders": {"host": self.host},
                "configuration_url": f"http://{self.host}:{self.port}",
            }
        )

        return await self.async_step_link()

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a Hass.io deCONZ bridge.

        This flow is triggered by the discovery component.
        """
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug("deCONZ HASSIO discovery %s", pformat(discovery_info.config))

        self.bridge_id = normalize_bridge_id(discovery_info.config[CONF_SERIAL])
        await self.async_set_unique_id(self.bridge_id)

        self.host = discovery_info.config[CONF_HOST]
        self.port = discovery_info.config[CONF_PORT]
        self.api_key = discovery_info.config[CONF_API_KEY]

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_API_KEY: self.api_key,
            }
        )

        self.context["configuration_url"] = HASSIO_CONFIGURATION_URL
        self._hassio_discovery = discovery_info.config

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a Hass.io discovery."""

        if user_input is not None:
            return await self._create_entry()

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
        )


class DeconzOptionsFlowHandler(OptionsFlow):
    """Handle deCONZ options."""

    gateway: DeconzHub

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the deCONZ options."""
        return await self.async_step_deconz_devices()

    async def async_step_deconz_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the deconz devices options."""
        if user_input is not None:
            return self.async_create_entry(data=self.config_entry.options | user_input)

        schema_options = {}
        for option, default in (
            (CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR),
            (CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS),
            (CONF_ALLOW_NEW_DEVICES, DEFAULT_ALLOW_NEW_DEVICES),
        ):
            schema_options[
                vol.Optional(
                    option,
                    default=self.config_entry.options.get(option, default),
                )
            ] = bool

        return self.async_show_form(
            step_id="deconz_devices",
            data_schema=vol.Schema(schema_options),
        )
