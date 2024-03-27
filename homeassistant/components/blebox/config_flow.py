"""Config flow for BleBox devices integration."""

from __future__ import annotations

import logging
from typing import Any

from blebox_uniapi.box import Box
from blebox_uniapi.error import (
    Error,
    UnauthorizedRequest,
    UnsupportedBoxResponse,
    UnsupportedBoxVersion,
)
from blebox_uniapi.session import ApiHost
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import get_maybe_authenticated_session
from .const import (
    ADDRESS_ALREADY_CONFIGURED,
    CANNOT_CONNECT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SETUP_TIMEOUT,
    DOMAIN,
    UNKNOWN,
    UNSUPPORTED_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def host_port(data):
    """Return a list with host and port."""
    return (data[CONF_HOST], data[CONF_PORT])


def create_schema(previous_input=None):
    """Create a schema with given values as default."""
    if previous_input is not None:
        host, port = host_port(previous_input)
    else:
        host = DEFAULT_HOST
        port = DEFAULT_PORT

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): int,
            vol.Inclusive(CONF_USERNAME, "auth"): str,
            vol.Inclusive(CONF_PASSWORD, "auth"): str,
        }
    )


LOG_MSG = {
    UNSUPPORTED_VERSION: "Outdated firmware",
    CANNOT_CONNECT: "Failed to identify device",
    UNKNOWN: "Unknown error while identifying device",
}


class BleBoxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BleBox devices."""

    VERSION = 1

    def __init__(self):
        """Initialize the BleBox config flow."""
        self.device_config = {}

    def handle_step_exception(
        self, step, exception, schema, host, port, message_id, log_fn
    ):
        """Handle step exceptions."""
        log_fn("%s at %s:%d (%s)", LOG_MSG[message_id], host, port, exception)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors={"base": message_id},
            description_placeholders={"address": f"{host}:{port}"},
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        hass = self.hass
        ipaddress = (discovery_info.host, discovery_info.port)
        self.device_config["host"] = discovery_info.host
        self.device_config["port"] = discovery_info.port

        websession = async_get_clientsession(hass)

        api_host = ApiHost(
            *ipaddress, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER
        )

        try:
            product = await Box.async_from_host(api_host)
        except UnsupportedBoxVersion:
            return self.async_abort(reason="unsupported_device_version")
        except UnsupportedBoxResponse:
            return self.async_abort(reason="unsupported_device_response")

        self.device_config["name"] = product.name
        # Check if configured but IP changed since
        await self.async_set_unique_id(product.unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
        self.context.update(
            {
                "title_placeholders": {
                    "name": self.device_config["name"],
                    "host": self.device_config["host"],
                },
                "configuration_url": f"http://{discovery_info.host}",
            }
        )
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirmation."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.device_config["name"],
                data={
                    "host": self.device_config["host"],
                    "port": self.device_config["port"],
                },
            )

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "name": self.device_config["name"],
                "host": self.device_config["host"],
                "port": self.device_config["port"],
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle initial user-triggered config step."""
        hass = self.hass
        schema = create_schema(user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors={},
                description_placeholders={},
            )

        addr = host_port(user_input)

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        for entry in self._async_current_entries():
            if addr == host_port(entry.data):
                host, port = addr
                return self.async_abort(
                    reason=ADDRESS_ALREADY_CONFIGURED,
                    description_placeholders={"address": f"{host}:{port}"},
                )

        websession = get_maybe_authenticated_session(hass, password, username)

        api_host = ApiHost(*addr, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER)
        try:
            product = await Box.async_from_host(api_host)

        except UnsupportedBoxVersion as ex:
            return self.handle_step_exception(
                "user", ex, schema, *addr, UNSUPPORTED_VERSION, _LOGGER.debug
            )
        except UnauthorizedRequest as ex:
            return self.handle_step_exception(
                "user", ex, schema, *addr, CANNOT_CONNECT, _LOGGER.error
            )

        except Error as ex:
            return self.handle_step_exception(
                "user", ex, schema, *addr, CANNOT_CONNECT, _LOGGER.warning
            )

        except RuntimeError as ex:
            return self.handle_step_exception(
                "user", ex, schema, *addr, UNKNOWN, _LOGGER.error
            )

        # Check if configured but IP changed since
        await self.async_set_unique_id(product.unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=product.name, data=user_input)
