"""Config flow for LEA Amp local."""

from __future__ import annotations

import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PORT

_LOGGER = logging.getLogger(__name__)


# Test Push
class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Init."""

        self.data: dict[str, str] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Step User."""

        # Specify items in the order they are to be displayed in the UI
        try:
            if user_input is not None:
                deviceName = getDeviceName(user_input["IP Address"])
                _LOGGER.log(logging.INFO, "deviceName %s", str(deviceName))
                if not deviceName:
                    _LOGGER.log(logging.INFO, "deviceName %s", str(deviceName))
                    raise ConfigEntryNotReady  # noqa: TRY301

                return self.async_create_entry(title=deviceName, data=user_input)

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("IP Address"): str,
                    }
                ),
            )
        except ConfigEntryNotReady:
            self.data["base"] = "cannot connect"
            return self.async_show_form(step_id="user", errors=self.data)


def getDeviceName(ip_address):
    """Get Num of inputs."""

    _LOGGER.log(logging.INFO, "Connect to %s", ip_address)
    msg = "get /amp/deviceInfo/deviceName\n"
    mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    address = (ip_address, int(PORT))
    try:
        mySocket.connect(address)

        mySocket.send(msg.encode())
        # while True:
        data = mySocket.recv(2048)
        if data:
            _LOGGER.log(logging.INFO, "response data: %s", str(data))
            data = data.decode()
            deviceName = data.replace("/amp/deviceInfo/deviceName", "")
            deviceName = deviceName.replace("\n", "")
            deviceName = deviceName.replace('"', "")
            mySocket.close()

            return deviceName
    except (TimeoutError, OSError, ConnectionRefusedError):
        return False
    finally:
        mySocket.close()
