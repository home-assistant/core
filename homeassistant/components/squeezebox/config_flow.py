"""Config flow for Logitech Squeezebox integration."""
import asyncio
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING

from pysqueezebox import Server, async_discover
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_registry import async_get

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 5


def _base_schema(discovery_info=None):
    """Generate base schema."""
    base_schema = {}
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
        {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): str}
    )
    return vol.Schema(base_schema)


class SqueezeboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logitech Squeezebox."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize an instance of the squeezebox config flow."""
        self.data_schema = _base_schema()
        self.discovery_info = None

    async def _discover(self, uuid=None):
        """Discover an unconfigured LMS server."""
        self.discovery_info = None
        discovery_event = asyncio.Event()

        def _discovery_callback(server):
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

    async def _validate_input(self, data):
        """Validate the user input allows us to connect.

        Retrieve unique id and abort if already configured.
        """
        server = Server(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_PORT],
            data.get(CONF_USERNAME),
            data.get(CONF_PASSWORD),
        )

        try:
            status = await server.async_query("serverstatus")
            if not status:
                if server.http_status == HTTPStatus.UNAUTHORIZED:
                    return "invalid_auth"
                return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            return "unknown"

        if "uuid" in status:
            await self.async_set_unique_id(status["uuid"])
            self._abort_if_unique_id_configured()

    async def async_step_user(self, user_input=None):
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
        except asyncio.TimeoutError:
            errors["base"] = "no_server_found"

        # display the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_edit(self, user_input=None):
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

    async def async_step_integration_discovery(self, discovery_info):
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
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle dhcp discovery of a Squeezebox player."""
        _LOGGER.debug(
            "Reached dhcp discovery of a player with info: %s", discovery_info
        )
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Configuring dhcp player with unique id: %s", self.unique_id)

        registry = async_get(self.hass)

        if TYPE_CHECKING:
            assert self.unique_id
        # if we have detected this player, do nothing. if not, there must be a server out there for us to configure, so start the normal user flow (which tries to autodetect server)
        if registry.async_get_entity_id(MP_DOMAIN, DOMAIN, self.unique_id) is not None:
            # this player is already known, so do nothing other than mark as configured
            raise data_entry_flow.AbortFlow("already_configured")

        # if the player is unknown, then we likely need to configure its server
        return await self.async_step_user()
