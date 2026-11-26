"""Config flow for the ADS integration."""

from collections.abc import Mapping
from functools import partial
import logging
from typing import Any, override

import probatio
import pyads

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN
from .hub import check_reachable

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): str,
        probatio.Optional(CONF_IP_ADDRESS): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    }
)


def _drop_blank_optionals(data: dict[str, Any]) -> dict[str, Any]:
    """Drop the IP address if it was left blank.

    A cleared field is submitted as an empty string, which pyads would take
    as an explicit value instead of deriving it from the AMS NetID.
    """
    return {
        key: value for key, value in data.items() if key != CONF_IP_ADDRESS or value
    }


def _is_valid_net_id(net_id: str) -> bool:
    """Return whether the AMS NetID is six numbers from 0 to 255, separated by dots."""
    parts = net_id.split(".")
    return len(parts) == 6 and all(
        # isdigit() alone accepts digits like "²" that int() rejects.
        part.isascii() and part.isdigit() and len(part) <= 3 and int(part) <= 255
        for part in parts
    )


def _host(data: Mapping[str, Any]) -> str:
    """Return the address pyads connects to, derived the same way pyads does."""
    return data.get(CONF_IP_ADDRESS) or ".".join(data[CONF_DEVICE].split(".")[:4])


def _validate_connection(data: dict[str, Any], *, reachable_only: bool) -> None:
    """Open a connection and read the device state.

    With reachable_only, only check the device accepts a TCP connection.
    """
    check_reachable(data[CONF_DEVICE], data.get(CONF_IP_ADDRESS))
    if reachable_only:
        return
    client = pyads.Connection(
        data[CONF_DEVICE], data[CONF_PORT], data.get(CONF_IP_ADDRESS)
    )
    client.open()
    try:
        # pyads returns None instead of raising when the port is closed.
        if client.read_state() is None:
            raise pyads.ADSError(err_code=1864)
    finally:
        client.close()


class AdsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADS."""

    VERSION = 1

    def _route_in_use(self, data: dict[str, Any]) -> bool:
        """Return whether the loaded hub holds a route to the NetID elsewhere.

        The AMS router keeps one route per NetID, so on Linux a second
        connection to it at another address is refused while the hub runs.
        The reload connects to the new address anyway.
        """
        if self.source != SOURCE_RECONFIGURE:
            return False
        entry = self._get_reconfigure_entry()
        return (
            entry.state is ConfigEntryState.LOADED
            and entry.data[CONF_DEVICE] == data[CONF_DEVICE]
            and _host(entry.data) != _host(data)
        )

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Validate the connection and return an error key on failure."""
        try:
            await self.hass.async_add_executor_job(
                partial(
                    _validate_connection,
                    data,
                    reachable_only=self._route_in_use(data),
                )
            )
        except pyads.ADSError, OSError, RuntimeError:
            # A device that does not answer raises OSError and the AMS router
            # refusing to open a port raises RuntimeError; setup treats both as
            # connectivity failures too.
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _drop_blank_optionals(user_input)
            if not _is_valid_net_id(user_input[CONF_DEVICE]):
                # Checked first: without an IP address the NetID also names
                # the host, and a malformed one would only fail to connect.
                errors[CONF_DEVICE] = "invalid_net_id"
            elif (error := await self._async_validate(user_input)) is None:
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=user_input[CONF_DEVICE],
                        data=user_input,
                    )
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE], data=user_input
                )
            else:
                errors["base"] = error

        suggested_values = user_input
        if suggested_values is None and self.source == SOURCE_RECONFIGURE:
            suggested_values = dict(self._get_reconfigure_entry().data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the ADS connection."""
        return await self.async_step_user(user_input)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the ADS connection from configuration.yaml.

        The connection is not tested here: a device that is offline when Home
        Assistant upgrades would otherwise leave the YAML entities without a
        connection. Setting up the entry retries until the device answers.
        """
        import_data = _drop_blank_optionals(import_data)
        if not _is_valid_net_id(import_data[CONF_DEVICE]):
            return self.async_abort(reason="invalid_net_id")
        return self.async_create_entry(title=import_data[CONF_DEVICE], data=import_data)
