"""Config flow for Squeezebox integration."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any

from pysqueezebox import Server, async_discover
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_BROWSE_LIMIT,
    CONF_HTTPS,
    CONF_VOLUME_STEP,
    DEFAULT_BROWSE_LIMIT,
    DEFAULT_PORT,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 5


def _base_schema(
    discovery_info: dict[str, Any] | None = None,
) -> vol.Schema:
    """Generate base schema."""
    base_schema: dict[Any, Any] = {}
    if discovery_info and CONF_HOST in discovery_info:
        base_schema.update(
            {
                vol.Required(
                    CONF_HOST,
                    description={"suggested_value": discovery_info[CONF_HOST]},
                ): str,
            }
        )
    else:
        base_schema.update({vol.Required(CONF_HOST): str})

    if discovery_info and CONF_PORT in discovery_info:
        base_schema.update(
            {
                vol.Required(
                    CONF_PORT,
                    default=DEFAULT_PORT,
                    description={"suggested_value": discovery_info[CONF_PORT]},
                ): int,
            }
        )
    else:
        base_schema.update({vol.Required(CONF_PORT, default=DEFAULT_PORT): int})

    base_schema.update(
        {
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_HTTPS, default=False): bool,
        }
    )

    return vol.Schema(base_schema)


class SqueezeboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Squeezebox."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize an instance of the squeezebox config flow."""
        self.data_schema = _base_schema()
        self.discovery_info: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def _discover(self, uuid: str | None = None) -> None:
        """Discover an unconfigured LMS server."""
        self.discovery_info = None
        discovery_event = asyncio.Event()

        def _discovery_callback(server: Server) -> None:
            if server.uuid:
                # ignore already configured uuids
                for entry in self._async_current_entries():
                    if entry.unique_id == server.uuid:
                        return
                self.discovery_info = {
                    CONF_HOST: server.host,
                    CONF_PORT: int(server.port),
                    "uuid": server.uuid,
                }
                _LOGGER.debug("Discovered server: %s", self.discovery_info)
                discovery_event.set()

        discovery_task = self.hass.async_create_task(
            async_discover(_discovery_callback)
        )

        await discovery_event.wait()
        discovery_task.cancel()  # stop searching as soon as we find server

        # update with suggested values from discovery
        self.data_schema = _base_schema(self.discovery_info)

    async def _validate_input(self, data: dict[str, Any]) -> str | None:
        """Validate the user input allows us to connect.

        Retrieve unique id and abort if already configured.
        """
        server = Server(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data.get(CONF_USERNAME),
            data.get(CONF_PASSWORD),
            https=data[CONF_HTTPS],
        )

        try:
            status = await server.async_query("serverstatus")
            if not status:
                if server.http_status == HTTPStatus.UNAUTHORIZED:
                    return "invalid_auth"
                return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unknown exception while validating connection")
            return "unknown"

        if "uuid" in status:
            await self.async_set_unique_id(status["uuid"])
            self._abort_if_unique_id_configured()

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input and CONF_HOST in user_input:
            # update with host provided by user
            self.data_schema = _base_schema(user_input)
            return await self.async_step_edit()

        # no host specified, see if we can discover an unconfigured LMS server
        try:
            async with asyncio.timeout(TIMEOUT):
                await self._discover()
            return await self.async_step_edit()
        except TimeoutError:
            errors["base"] = "no_server_found"

        # display the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a discovered or manually inputted server."""
        errors = {}
        if user_input:
            error = await self._validate_input(user_input)
            if not error:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="edit", data_schema=self.data_schema, errors=errors
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle discovery of a server."""
        _LOGGER.debug("Reached server discovery flow with info: %s", discovery_info)
        if "uuid" in discovery_info:
            await self.async_set_unique_id(discovery_info.pop("uuid"))
            self._abort_if_unique_id_configured()
        else:
            # attempt to connect to server and determine uuid. will fail if
            # password required
            error = await self._validate_input(discovery_info)
            if error:
                await self._async_handle_discovery_without_unique_id()

        # update schema with suggested values from discovery
        self.data_schema = _base_schema(discovery_info)

        self.context.update({"title_placeholders": {"host": discovery_info[CONF_HOST]}})

        return await self.async_step_edit()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery of a Squeezebox player."""
        _LOGGER.debug(
            "Reached dhcp discovery of a player with info: %s", discovery_info
        )
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Configuring dhcp player with unique id: %s", self.unique_id)

        registry = er.async_get(self.hass)

        if TYPE_CHECKING:
            assert self.unique_id
        # if we have detected this player, do nothing. if not, there must be a server out there for us to configure, so start the normal user flow (which tries to autodetect server)
        if registry.async_get_entity_id(MP_DOMAIN, DOMAIN, self.unique_id) is not None:
            # this player is already known, so do nothing other than mark as configured
            raise AbortFlow("already_configured")

        # if the player is unknown, then we likely need to configure its server
        return await self.async_step_user()


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BROWSE_LIMIT): vol.All(
            NumberSelector(
                NumberSelectorConfig(min=1, max=65534, mode=NumberSelectorMode.BOX)
            ),
            vol.Coerce(int),
        ),
        vol.Required(CONF_VOLUME_STEP): vol.All(
            NumberSelector(
                NumberSelectorConfig(min=1, max=20, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Coerce(int),
        ),
    }
)


class OptionsFlowHandler(OptionsFlow):
    """Options Flow Handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options Flow Steps."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_BROWSE_LIMIT: self.config_entry.options.get(
                        CONF_BROWSE_LIMIT, DEFAULT_BROWSE_LIMIT
                    ),
                    CONF_VOLUME_STEP: self.config_entry.options.get(
                        CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP
                    ),
                },
            ),
        )
