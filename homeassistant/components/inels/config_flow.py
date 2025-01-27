"""Config flow for iNELS."""

from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.const import MQTT_TRANSPORT
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, TITLE

CONNECTION_TIMEOUT = 5


class INelsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle of iNELS config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input:
            # Abort if an entry with the same host already exists
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            test_connect = await self.hass.async_add_executor_job(
                try_connection,
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_USERNAME, ""),
                user_input.get(CONF_PASSWORD, ""),
                user_input[MQTT_TRANSPORT],
            )

            if test_connect is None:
                return self.async_create_entry(
                    title=f"{TITLE} ({user_input[CONF_HOST]})",
                    data=user_input,
                )

            errors["base"] = connect_val_to_error(test_connect)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=1883): vol.Coerce(int),
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(MQTT_TRANSPORT, default="tcp"): vol.In(
                        ["tcp", "websockets"]
                    ),
                }
            ),
            errors=errors,
        )


def try_connection(
    hass: HomeAssistant,
    host: str,
    port: int,
    username: str,
    password: str,
    transport: str = "tcp",
) -> int | None:
    """Test if we can connect to an MQTT broker."""
    entry_config = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        MQTT_TRANSPORT: transport,
    }
    client = InelsMqtt(entry_config)
    ret: int | None = client.test_connection()
    client.disconnect()

    return ret


TEST_CONNECT_ERRORS: dict[int, str] = {
    1: "mqtt_version",
    2: "forbidden_id",  # should never happen
    3: "cannot_connect",
    4: "invalid_auth",
    5: "unauthorized",
}


def connect_val_to_error(test_connect: int | None) -> str:
    """Turn test_connect value into an error string."""
    if test_connect in TEST_CONNECT_ERRORS:
        return TEST_CONNECT_ERRORS[test_connect]
    return "unknown"
