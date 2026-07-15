"""Config flow to configure russound_rio component."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import (
    RussoundConnectionHandler,
    RussoundSerialConnectionHandler,
)
from aiorussound.rio import Controller, RussoundRIOClient
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SerialSelector,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_BAUDRATE,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DOMAIN,
    RUSSOUND_RIO_EXCEPTIONS,
    TYPE_SERIAL,
    TYPE_TCP,
)

TRANSPORT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE, default=TYPE_TCP): SelectSelector(
            SelectSelectorConfig(
                options=[TYPE_TCP, TYPE_SERIAL],
                translation_key="connection_type",
            )
        ),
    }
)

TCP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialSelector(),
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
            vol.Coerce(int),
            vol.Range(min=1),
        ),
    }
)


_LOGGER = logging.getLogger(__name__)


async def _async_validate_connection(
    connection_handler: RussoundConnectionHandler,
) -> Controller | None:
    """Validate a Russound connection and return the controller."""
    client = RussoundRIOClient(connection_handler)
    try:
        await client.connect()
        controller = client.controllers[1]
    except RUSSOUND_RIO_EXCEPTIONS:
        return None
    finally:
        with suppress(*RUSSOUND_RIO_EXCEPTIONS):
            await client.disconnect()
    return controller


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Russound RIO configuration flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def _async_finish_manual_setup(
        self, controller: Controller, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Finish manual setup or reconfigure after validation."""
        await self.async_set_unique_id(
            controller.mac_address,
            raise_on_progress=False,
        )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="wrong_device")
            entry = self._get_reconfigure_entry()
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=controller.controller_type,
            data=data,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.data[CONF_HOST] = host = discovery_info.host
        self.data[CONF_PORT] = port = discovery_info.port or 9621

        controller = await _async_validate_connection(
            RussoundTcpConnectionHandler(host, port)
        )
        if not controller:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(controller.mac_address)
        self._abort_if_unique_id_configured(
            updates={CONF_TYPE: TYPE_TCP, CONF_HOST: host, CONF_PORT: port}
        )

        self.data[CONF_NAME] = controller.controller_type

        self.context["title_placeholders"] = {
            "name": self.data[CONF_NAME],
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.data[CONF_NAME],
                data={
                    CONF_TYPE: TYPE_TCP,
                    CONF_HOST: self.data[CONF_HOST],
                    CONF_PORT: self.data[CONF_PORT],
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.data[CONF_NAME],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=TRANSPORT_SCHEMA,
            )

        self.data[CONF_TYPE] = user_input[CONF_TYPE]
        if user_input[CONF_TYPE] == TYPE_TCP:
            return await self.async_step_tcp()
        return await self.async_step_serial()

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle TCP configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            controller = await _async_validate_connection(
                RussoundTcpConnectionHandler(host, port)
            )
            if controller is None:
                _LOGGER.exception("Could not connect to Russound RIO over TCP")
                errors["base"] = "cannot_connect"
            else:
                data = {CONF_TYPE: TYPE_TCP, CONF_HOST: host, CONF_PORT: port}
                return await self._async_finish_manual_setup(controller, data)

        return self.async_show_form(
            step_id="tcp", data_schema=TCP_SCHEMA, errors=errors
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle serial configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = user_input[CONF_DEVICE]
            baudrate = user_input[CONF_BAUDRATE]

            controller = await _async_validate_connection(
                RussoundSerialConnectionHandler(device, baudrate)
            )
            if controller is None:
                _LOGGER.exception("Could not connect to Russound RIO over serial")
                errors["base"] = "cannot_connect"
            else:
                data = {
                    CONF_TYPE: TYPE_SERIAL,
                    CONF_DEVICE: device,
                    CONF_BAUDRATE: baudrate,
                }
                return await self._async_finish_manual_setup(controller, data)

        return self.async_show_form(
            step_id="serial", data_schema=SERIAL_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        return await self.async_step_user(user_input)
