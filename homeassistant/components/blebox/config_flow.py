"""Config flow for BleBox devices integration."""

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

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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


STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
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

    def __init__(self) -> None:
        """Initialize the BleBox config flow."""
        self.device_config: dict[str, Any] = {}

    def handle_step_exception(
        self, exception, schema, host, port, message_id, log_fn, step_id
    ):
        """Handle step exceptions."""
        log_fn("%s at %s:%d (%s)", LOG_MSG[message_id], host, port, exception)

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors={"base": message_id},
            description_placeholders={"address": f"{host}:{port}"},
        )

    async def _async_from_host_or_form(
        self, api_host: ApiHost, user_input: dict[str, Any], step_id: str
    ) -> tuple[Box, None] | tuple[None, ConfigFlowResult]:
        """Try to connect to the device; return product or an error form."""
        schema = self.add_suggested_values_to_schema(STEP_SCHEMA, user_input)
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        try:
            return await Box.async_from_host(api_host), None
        except UnsupportedBoxVersion as ex:
            return None, self.handle_step_exception(
                ex, schema, host, port, UNSUPPORTED_VERSION, _LOGGER.debug, step_id
            )
        except UnauthorizedRequest as ex:
            return None, self.handle_step_exception(
                ex, schema, host, port, CANNOT_CONNECT, _LOGGER.error, step_id
            )
        except Error as ex:
            return None, self.handle_step_exception(
                ex, schema, host, port, CANNOT_CONNECT, _LOGGER.warning, step_id
            )
        except RuntimeError as ex:
            return None, self.handle_step_exception(
                ex, schema, host, port, UNKNOWN, _LOGGER.error, step_id
            )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial user-triggered config step."""
        hass = self.hass

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_SCHEMA,
                errors={},
                description_placeholders={},
            )

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        for entry in self._async_current_entries():
            if host == entry.data[CONF_HOST] and port == entry.data[CONF_PORT]:
                return self.async_abort(
                    reason=ADDRESS_ALREADY_CONFIGURED,
                    description_placeholders={"address": f"{host}:{port}"},
                )

        websession = get_maybe_authenticated_session(hass, password, username)

        api_host = ApiHost(
            host, port, DEFAULT_SETUP_TIMEOUT, websession, hass.loop, _LOGGER
        )
        product, error = await self._async_from_host_or_form(
            api_host, user_input, step_id="user"
        )
        if error is not None:
            return error
        assert product is not None

        # Check if configured but IP changed since
        await self.async_set_unique_id(product.unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=product.name, data=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of a BleBox device."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_SCHEMA, reconfigure_entry.data
                ),
            )

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)
        websession = get_maybe_authenticated_session(self.hass, password, username)
        api_host = ApiHost(
            host, port, DEFAULT_SETUP_TIMEOUT, websession, self.hass.loop, _LOGGER
        )

        product, error = await self._async_from_host_or_form(
            api_host, user_input, step_id="reconfigure"
        )
        if error is not None:
            return error
        assert product is not None

        await self.async_set_unique_id(product.unique_id)
        self._abort_if_unique_id_mismatch()

        data_updates: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
        if username is not None:
            data_updates[CONF_USERNAME] = username
        if password is not None:
            data_updates[CONF_PASSWORD] = password

        return self.async_update_reload_and_abort(
            reconfigure_entry,
            data_updates=data_updates,
        )
