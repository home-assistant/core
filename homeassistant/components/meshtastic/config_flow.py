"""Config flow for the Meshtastic integration."""

import asyncio
import socket
from typing import TYPE_CHECKING, Any, Final, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import MeshtasticClient, MeshtasticError
from .const import (
    CONF_DOWNLOAD_NODE_DB,
    CONF_INCLUDE_LOCATION,
    CONF_TRACK_POSITION,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_DOWNLOAD_NODE_DB,
    DEFAULT_INCLUDE_LOCATION,
    DEFAULT_PORT,
    DEFAULT_TRACK_POSITION,
    DOMAIN,
    LOGGER,
    format_node_id,
)
from .models import GatewayInfo

#: Upper bound on the connection test.  Much shorter than the runtime
#: CONNECT_TIMEOUT: someone waiting in front of a form deserves a quick answer.
VALIDATION_TIMEOUT: Final = 20.0

STEP_USER_DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_DOWNLOAD_NODE_DB, default=DEFAULT_DOWNLOAD_NODE_DB): bool,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

OPTIONS_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_DOWNLOAD_NODE_DB, default=DEFAULT_DOWNLOAD_NODE_DB): bool,
        vol.Required(CONF_TRACK_POSITION, default=DEFAULT_TRACK_POSITION): bool,
        vol.Required(CONF_INCLUDE_LOCATION, default=DEFAULT_INCLUDE_LOCATION): bool,
    }
)


class _ProbeFailed(Exception):
    """A connection test failed, carrying the error key to show the user."""

    def __init__(self, key: str) -> None:
        """Store the config flow error key."""
        super().__init__(key)
        self.key = key


def _error_key(err: MeshtasticError) -> str:
    """Return the config flow error key for a client error."""
    cause = err.__cause__
    if isinstance(cause, socket.gaierror):
        return "invalid_host"
    if isinstance(cause, (ConnectionResetError, BrokenPipeError)):
        # The firmware serves one API client at a time and force-closes the one
        # it drops, which is what a reset during the handshake means.
        return "already_in_use"
    if err.translation_key == "timeout":
        return "timeout_connect"
    return "cannot_connect"


class MeshtasticConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meshtastic."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    async def _async_probe(self, host: str, port: int) -> GatewayInfo:
        """Connect to a node once and return the identity it reported.

        The node database is never downloaded here, whatever the user asked
        for: a memory constrained node can crash while dumping it, and setting
        the integration up must not be the thing that knocks it over.
        """
        client = MeshtasticClient(self.hass, host, port, download_node_db=False)
        try:
            async with asyncio.timeout(VALIDATION_TIMEOUT):
                await client.async_start()
            gateway = client.gateway
        except TimeoutError as err:
            raise _ProbeFailed("timeout_connect") from err
        except MeshtasticError as err:
            LOGGER.debug(
                "Could not connect to the Meshtastic node at %s: %s", host, err
            )
            raise _ProbeFailed(_error_key(err)) from err
        except Exception as err:
            LOGGER.exception("Unexpected error connecting to the node at %s", host)
            raise _ProbeFailed("unknown") from err
        finally:
            await client.async_stop()

        if TYPE_CHECKING:
            assert gateway is not None
        return gateway

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors["base"] = "invalid_host"
            else:
                try:
                    gateway = await self._async_probe(host, user_input[CONF_PORT])
                except _ProbeFailed as err:
                    errors["base"] = err.key
                else:
                    await self.async_set_unique_id(format_node_id(gateway.node_num))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=gateway.name,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: user_input[CONF_PORT],
                            CONF_DOWNLOAD_NODE_DB: user_input[CONF_DOWNLOAD_NODE_DB],
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point an existing entry at a new address for the same node."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors["base"] = "invalid_host"
            else:
                try:
                    gateway = await self._async_probe(host, user_input[CONF_PORT])
                except _ProbeFailed as err:
                    errors["base"] = err.key
                else:
                    await self.async_set_unique_id(
                        format_node_id(gateway.node_num), raise_on_progress=False
                    )
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry,
                        title=gateway.name,
                        data_updates={
                            CONF_HOST: host,
                            CONF_PORT: user_input[CONF_PORT],
                        },
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA,
                user_input
                or {
                    CONF_HOST: entry.data[CONF_HOST],
                    CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
                },
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return MeshtasticOptionsFlow()


class MeshtasticOptionsFlow(OptionsFlowWithReload):
    """Handle the Meshtastic runtime options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    # The node database flag was collected in the user step
                    # before it became an option, so the entry data is the
                    # fallback for an entry created back then.
                    CONF_DOWNLOAD_NODE_DB: entry.options.get(
                        CONF_DOWNLOAD_NODE_DB,
                        entry.data.get(CONF_DOWNLOAD_NODE_DB, DEFAULT_DOWNLOAD_NODE_DB),
                    ),
                    CONF_TRACK_POSITION: entry.options.get(
                        CONF_TRACK_POSITION, DEFAULT_TRACK_POSITION
                    ),
                    CONF_INCLUDE_LOCATION: entry.options.get(
                        CONF_INCLUDE_LOCATION, DEFAULT_INCLUDE_LOCATION
                    ),
                },
            ),
        )
