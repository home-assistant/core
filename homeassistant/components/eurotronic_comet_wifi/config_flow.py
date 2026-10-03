"""Config flow for the Eurotronic Comet WiFi integration."""

from asyncio import sleep
import logging
from typing import Any, override

from aiocometwifi import CometWifiConnectionError, CometWifiValueError, Thermostat
import probatio

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DEVICE_NAME_PREFIX, DOMAIN, FETCH_DATA_TIMEOUT
from .transport import get_mqtt_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_MAC): str})


async def validate_input(hass: HomeAssistant, mac: str) -> str:
    """Make sure the thermostat answers and return its normalized MAC address.

    Raises CometWifiValueError for a malformed MAC address and CannotConnect
    when the thermostat does not reply.
    """

    client = Thermostat(get_mqtt_client(hass), mac)
    try:
        await client.connect()
        # Give the device time to answer
        await sleep(FETCH_DATA_TIMEOUT)
        connected = client.connected
    except CometWifiConnectionError as err:
        raise CannotConnect from err
    finally:
        await client.disconnect()

    if not connected:
        raise CannotConnect

    return client.mac


class CometWiFiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eurotronic Comet WiFi."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        try:
            if not mqtt.is_connected(self.hass):
                return self.async_abort(reason="mqtt_not_connected")
        except KeyError:
            return self.async_abort(reason="mqtt_not_configured")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = await validate_input(self.hass, user_input[CONF_MAC])
            except CometWifiValueError:
                errors[CONF_MAC] = "invalid_mac"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{DEVICE_NAME_PREFIX} {mac}", data={CONF_MAC: mac}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
