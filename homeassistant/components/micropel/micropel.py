"""Support for Micropel."""
import logging

from pymicropel.communicator.mpc_300 import Mpc300
from pymicropel.communicator.mpc_400 import Mpc400
from pymicropel.helper.crypto import Crypto

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import HomeAssistantError

from ...core import Event
from .const import (
    COMMUNICATOR_TYPE_MPC300,
    COMMUNICATOR_TYPE_MPC400,
    CONF_COMMUNICATOR_TYPE,
    CONF_CONNECTION_TCP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MicropelModule:
    """Thread safe wrapper."""

    def __init__(self, hass, config):
        """Initialize the Micropel hub."""

        self.connected = False
        self.hass = hass
        self.config = config

        # TCP network configuration
        self._config_host = self.config[DOMAIN][CONF_CONNECTION_TCP][CONF_HOST]
        self._config_port = self.config[DOMAIN][CONF_CONNECTION_TCP][CONF_PORT]
        self._config_password = self.config[DOMAIN][CONF_CONNECTION_TCP][CONF_PASSWORD]
        self._config_communicator_type = self.config[DOMAIN][CONF_CONNECTION_TCP][
            CONF_COMMUNICATOR_TYPE
        ]

        # Cryptography
        self._cryptography = Crypto()
        self._cryptography.crypt_init(self._config_password)

        # network configuration - TcpClient
        if self._config_communicator_type == COMMUNICATOR_TYPE_MPC300:
            self._communicator = Mpc300(
                self._config_host, self._config_port, self._config_password
            )
        elif self._config_communicator_type == COMMUNICATOR_TYPE_MPC400:
            self._communicator = Mpc400(
                self._config_host, self._config_port, self._config_password
            )
        else:
            _LOGGER.error(
                "Unknown communicator_type %s. You can select from 'MPC300' and ' MPC400'",
                self._config_communicator_type,
            )
            raise HomeAssistantError

    async def start(self) -> None:
        """Start Micropel object. Connect to Micropel device."""
        self._communicator.connect()
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.connected = True

    async def stop(self, event: Event) -> None:
        """Stop XKNX object. Disconnect from tunneling or Routing device."""
        self._communicator.close()
        self.connected = False

    def read_word(self, plc, address):
        """Read word from PLC."""
        return self._communicator.read_word(plc, address)

    def write_word(self, plc, address, value: int):
        """Write word to PLC."""
        return self._communicator.write_word(plc, address, value)

    def read_bit(self, plc, address, mask):
        """Read boolean from PLC."""
        return self._communicator.read_bit(plc, address, mask)

    def write_bit(self, plc, address, mask, value: bool):
        """Write boolean to PLC."""
        return self._communicator.write_bit(plc, address, mask, value)
