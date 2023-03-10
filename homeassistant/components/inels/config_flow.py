"""Config flow for iNELS."""
from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.hassio.discovery import HassioServiceInfo
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, TITLE

CONNECTION_TIMEOUT = 5


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle of iNELS config flow."""

    VERSION = 1

    _hassio_discovery: dict[str, Any] | None = None

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
        errors: dict[str, str] = {}

        if user_input is not None:
            test_connect = await self.hass.async_add_executor_job(
                try_connection,
                self.hass,
                user_input.get(CONF_HOST),
                user_input.get(CONF_PORT),
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                user_input.get(MQTT_TRANSPORT),
            )

            if test_connect is None:
                user_input[CONF_DISCOVERY] = True
                return self.async_create_entry(
                    title=TITLE,
                    data={
                        CONF_HOST: user_input.get(CONF_HOST),
                        CONF_PORT: user_input.get(CONF_PORT),
                        CONF_USERNAME: user_input.get(CONF_USERNAME),
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                        MQTT_TRANSPORT: user_input.get(MQTT_TRANSPORT),
                        CONF_DISCOVERY: True,
                    },
                )

            errors["base"] = connect_val_to_error(test_connect)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="setup",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_PORT,
                        default=1883
                        if user_input.get(CONF_PORT) is None
                        else user_input.get(CONF_PORT),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)
                    ): str,
                    vol.Required(MQTT_TRANSPORT, default="tcp"): vol.In(
                        ["tcp", "websockets"]
                    ),
                }
            ),
            errors=errors,
            last_step=True,
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
                data.get(CONF_HOST),
                data.get(CONF_PORT),
                data.get(CONF_USERNAME),
                data.get(CONF_PASSWORD),
                data.get(MQTT_TRANSPORT),
            )

            if test_connect is None:
                return self.async_create_entry(
                    title=TITLE,
                    data={
                        CONF_HOST: data.get(CONF_HOST),
                        CONF_PORT: data.get(CONF_PORT),
                        CONF_USERNAME: data.get(CONF_USERNAME),
                        CONF_PASSWORD: data.get(CONF_PASSWORD),
                        MQTT_TRANSPORT: data.get(MQTT_TRANSPORT),
                        CONF_DISCOVERY: True,
                    },
                )

            errors["base"] = connect_val_to_error(test_connect)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors,
        )


def try_connection(
    hass: HomeAssistant,
    host: str,
    port: str,
    username: str,
    password: str,
    transfer: str = "tcp",
):
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


TEST_CONNECT_ERRORS: dict[int, str] = {
    1: "mqtt_version",
    2: "forbidden_id",  # should never happen
    3: "cannot_connect",
    4: "invalid_auth",
    5: "unauthorized",
}


def connect_val_to_error(test_connect: int | None):
    """Turn test_connect value into an error string."""
    if test_connect in TEST_CONNECT_ERRORS:
        return TEST_CONNECT_ERRORS[test_connect]
    return "unknown"
