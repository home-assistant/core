"""Config flow for iNels."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio.discovery import HassioServiceInfo
from homeassistant.components.mqtt.const import DEFAULT_DISCOVERY
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, TITLE

CONNECTION_TIMEOUT = 5


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle of Inels config flow."""

    VERSION = 1

    _hassio_discovery = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> InelsOptionsFlowHandler:
        """Get the options flow for this handler."""
        return InelsOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow by user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_setup()

    async def async_step_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the setup."""
        errors = {}

        if user_input is not None:
            test_connect = await self.hass.async_add_executor_job(
                try_connection,
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                user_input.get(MQTT_TRANSPORT),
            )

            if test_connect:
                user_input[CONF_DISCOVERY] = DEFAULT_DISCOVERY
                return self.async_create_entry(
                    title=TITLE,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_USERNAME: user_input.get(CONF_USERNAME),
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                        MQTT_TRANSPORT: user_input.get(MQTT_TRANSPORT),
                        CONF_DISCOVERY: DEFAULT_DISCOVERY,
                    },
                )

            errors["base"] = "cannot_connect"
        else:
            user_input = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_HOST, default=user_input.get(CONF_HOST))] = str
        fields[
            vol.Required(
                CONF_PORT,
                default=1883
                if user_input.get(CONF_PORT) is None
                else user_input.get(CONF_PORT),
            )
        ] = vol.Coerce(int)
        fields[vol.Optional(CONF_USERNAME, default=user_input.get(CONF_USERNAME))] = str
        fields[vol.Optional(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD))] = str
        fields[vol.Required(MQTT_TRANSPORT, default="tcp")] = vol.In(
            ["tcp", "websockets"]
        )

        return self.async_show_form(
            step_id="setup", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Receive a Hass.io discovery."""
        await self._async_handle_discovery_without_unique_id()
        self._hassio_discovery = discovery_info.config

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovery."""
        errors = {}
        assert self._hassio_discovery

        if user_input is not None:
            data = self._hassio_discovery
            test_connect = await self.hass.async_add_executor_job(
                try_connection,
                self.hass,
                data[CONF_HOST],
                data[CONF_PORT],
                data.get(CONF_USERNAME),
                data.get(CONF_PASSWORD),
                data.get(MQTT_TRANSPORT),
            )

            if test_connect:
                return self.async_create_entry(
                    title=TITLE,
                    data={
                        CONF_HOST: data[CONF_HOST],
                        CONF_PORT: data[CONF_PORT],
                        CONF_USERNAME: data.get(CONF_USERNAME),
                        CONF_PASSWORD: data.get(CONF_PASSWORD),
                        MQTT_TRANSPORT: data.get(MQTT_TRANSPORT),
                        CONF_DISCOVERY: DEFAULT_DISCOVERY,
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors,
        )


class InelsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Inels options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.broker_config: dict[str, str | int] = {}
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        """Manage the MQTT setup."""
        return await self.async_step_setup()

    async def async_step_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the MQTT configuration to connect."""
        errors = {}
        current_config = self.config_entry.data

        if user_input is not None:
            test_connect = await self.hass.async_add_executor_job(
                try_connection,
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                user_input.get(MQTT_TRANSPORT),
            )

            if test_connect:
                self.broker_config.update(user_input)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.broker_config
                )
                return self.async_create_entry(
                    title=TITLE,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_USERNAME: user_input.get(CONF_USERNAME),
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                        MQTT_TRANSPORT: user_input.get(MQTT_TRANSPORT),
                        CONF_DISCOVERY: DEFAULT_DISCOVERY,
                    },
                )

            errors["base"] = "cannot_connect"

        fields = OrderedDict()
        current_broker = current_config.get(CONF_HOST)
        current_port = current_config.get(CONF_PORT)
        current_user = current_config.get(CONF_USERNAME)
        current_pass = current_config.get(CONF_PASSWORD)
        current_transport = current_config.get(MQTT_TRANSPORT)
        fields[vol.Required(CONF_HOST, default=current_broker)] = str
        fields[vol.Required(CONF_PORT, default=current_port)] = vol.Coerce(int)
        fields[
            vol.Optional(
                CONF_USERNAME,
                description={"suggested_value": current_user},
            )
        ] = str
        fields[
            vol.Optional(
                CONF_PASSWORD,
                description={"suggested_value": current_pass},
            )
        ] = str
        fields[vol.Required(MQTT_TRANSPORT, default=current_transport)] = vol.In(
            ["tcp", "websockets"]
        )

        return self.async_show_form(
            step_id="setup",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=True,
        )


def try_connection(hass, host, port, username, password, transfer="tcp"):
    """Test if we can connect to an MQTT broker."""
    entry_config = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        MQTT_TRANSPORT: transfer,
    }
    client = InelsMqtt(entry_config)
    ret = client.test_connection()
    client.disconnect()

    return ret
