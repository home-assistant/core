"""Support for Micropel."""
import logging

from homeassistant.const import (
    ATTR_STATE,
    CONF_ADDRESS,
    CONF_COVERS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery import load_platform

from .communicator.mpc_300 import Mpc300
from .communicator.mpc_400 import Mpc400
from .const import (
    ATTR_VALUE,
    COMMUNICATOR_TYPE_MPC300,
    COMMUNICATOR_TYPE_MPC400,
    CONF_CLIMATE,
    CONF_CLIMATES,
    CONF_COMMUNICATOR_TYPE,
    CONF_COVER,
    CONF_HUB,
    CONF_PLC,
    DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from .helper.crypto import Crypto

_LOGGER = logging.getLogger(__name__)


def micropel_setup(
    hass, config, service_write_register_schema, service_write_coil_schema
):
    """Set up Micropel component."""
    hass.data[DOMAIN] = hub_collect = {}

    for conf_hub in config[DOMAIN]:
        hub_collect[conf_hub[CONF_NAME]] = MicropelHub(conf_hub)

        # Micropel needs to be activated before components are loaded
        # to avoid a racing problem
        hub_collect[conf_hub[CONF_NAME]].setup()

        # load platforms
        for component, conf_key in (
            (CONF_CLIMATE, CONF_CLIMATES),
            (CONF_COVER, CONF_COVERS),
        ):
            if conf_key in conf_hub:
                load_platform(hass, component, DOMAIN, conf_hub, config)

    def stop_micropel(event):
        """Stop Micropel service."""
        for hub in hub_collect.values():
            hub.close()

    def write_register(service):
        """Write Micropel registers."""
        unit = int(float(service.data[CONF_PLC]))
        address = int(float(service.data[CONF_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = service.data[CONF_HUB]
        if isinstance(value, list):
            hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value]
            )
        else:
            hub_collect[client_name].write_register(unit, address, int(float(value)))

    def write_coil(service):
        """Write Micropel coil."""
        unit = service.data[CONF_PLC]
        address = service.data[CONF_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = service.data[CONF_HUB]
        hub_collect[client_name].write_coil(unit, address, state)

    # register function to gracefully stop micropel
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_micropel)

    # Register services for micropel
    hass.services.register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        write_register,
        schema=service_write_register_schema,
    )
    hass.services.register(
        DOMAIN, SERVICE_WRITE_COIL, write_coil, schema=service_write_coil_schema
    )
    return True


class MicropelHub:
    """Thread safe wrapper."""

    def __init__(self, client_config):
        """Initialize the Micropel hub."""

        # generic configuration
        self._config_name = client_config[CONF_NAME]
        self._config_port = client_config[CONF_PORT]
        self._config_password = client_config[CONF_PASSWORD]
        self._config_communicator_type = client_config[CONF_COMMUNICATOR_TYPE]

        # Cryptography
        self._cryptography = Crypto()
        self._cryptography.crypt_init(self._config_password)

        # network configuration
        self._config_host = client_config[CONF_HOST]

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

    @property
    def name(self):
        """Return the name of this hub."""
        return self._config_name

    def setup(self):
        """Set up TCP/IP client."""
        self.connect()

    def close(self):
        """Disconnect client."""
        self._communicator.close()

    def connect(self):
        """Connect client."""
        self._communicator.connect()

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
