"""Config flow for Eway integration."""

from __future__ import annotations

import logging
from typing import Any

from aioeway import device_mqtt_client
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SN,
    CONF_KEEPALIVE,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_HOST, default="localhost"): str,
        vol.Required(CONF_MQTT_PORT, default=1883): int,
        vol.Required(CONF_MQTT_USERNAME): str,
        vol.Required(CONF_MQTT_PASSWORD): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DEVICE_SN): str,
        vol.Required(CONF_DEVICE_MODEL): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Required(CONF_KEEPALIVE, default=60): int,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        # Import aioeway here to test connection
        # import aioeway

        client = device_mqtt_client.DeviceMQTTClient(
            device_model=data[CONF_DEVICE_MODEL],
            device_sn=data[CONF_DEVICE_SN],
            username=data.get(CONF_MQTT_USERNAME),
            password=data.get(CONF_MQTT_PASSWORD),
            broker_host=data[CONF_MQTT_HOST],
            broker_port=data[CONF_MQTT_PORT],
            use_tls=True,
            keepalive=data[CONF_KEEPALIVE],
        )

        # Test connection
        try:
            await client.connect()
        finally:
            await client.disconnect()

    except ConnectionError as err:
        raise CannotConnect from err

    except Exception as err:
        raise CannotConnect from err

    return {"title": f"Eway Inverter {data['device_id']}"}


class EwayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eway."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Check for existing entries with the same device_sn
            await self.async_set_unique_id(user_input[CONF_DEVICE_SN])
            self._abort_if_unique_id_configured()
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
