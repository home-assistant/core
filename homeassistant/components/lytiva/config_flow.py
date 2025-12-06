"""Config flow for Lytiva integration."""
from typing import Any
import voluptuous as vol
import logging
import paho.mqtt.client as mqtt_client
from .const import DOMAIN  # ✅ Import from const.py

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)

class LytivaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lytiva."""
    
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            connection_result = await self._test_connection(
                user_input["broker"],
                user_input.get("port", 1883),
                user_input.get("username"),
                user_input.get("password")
            )
            
            if connection_result == "success":
                await self.async_set_unique_id(f"lytiva_{user_input['broker']}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"Lytiva ({user_input['broker']})",
                    data=user_input,
                )
            elif connection_result == "auth_error":
                errors["base"] = "invalid_auth"
            elif connection_result == "cannot_connect":
                errors["base"] = "cannot_connect"
            else:
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("broker"): str,
                vol.Optional("port", default=1883): int,
                vol.Optional("username", default=""): str,
                vol.Optional("password", default=""): str,
            }),
            errors=errors,
            description_placeholders={
                "broker": "MQTT Broker IP address (e.g., 192.168.1.100)",
                "port": "MQTT Port (usually 1883)",
            }
        )
    
    async def _test_connection(self, broker: str, port: int, username: str, password: str) -> str:
        """Test MQTT connection."""
        result = {"status": "unknown"}
        
        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                result["status"] = "success"
            elif reason_code == 4:
                result["status"] = "auth_error"
            else:
                result["status"] = "cannot_connect"
            client.disconnect()
        
        try:
            test_client = mqtt_client.Client(
                client_id="lytiva_test",
                callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2
            )
            test_client.on_connect = on_connect
            if username:
                test_client.username_pw_set(username, password)
            
            await self.hass.async_add_executor_job(test_client.connect, broker, port, 10)
            await self.hass.async_add_executor_job(test_client.loop, 2)
            return result["status"]
        except Exception as e:
            _LOGGER.error("MQTT connection test failed: %s", e)
            return "cannot_connect"
