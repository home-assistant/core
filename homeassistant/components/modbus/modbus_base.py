"""Base class for the Modbus client and server."""
from abc import ABC, abstractmethod
import threading

from homeassistant.const import CONF_NAME, CONF_PORT, CONF_TIMEOUT, CONF_TYPE


class BaseModbusHub(ABC):
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, client_config):
        """Initialize the Modbus hub."""

        # generic configuration
        self._lock = threading.Lock()
        self._config_name = client_config[CONF_NAME]
        self._config_type = client_config[CONF_TYPE]
        self._config_port = client_config[CONF_PORT]
        self._config_timeout = client_config[CONF_TIMEOUT]
        self._config_delay = 0

    @property
    def name(self):
        """Return the name of this hub."""
        return self._config_name

    @abstractmethod
    def setup(self):
        """Modbus hub setup."""
        assert False

    @abstractmethod
    def close(self):
        """Disconnect client."""
        assert False

    @abstractmethod
    def read_coils(self, unit, address, count):
        """Read coils."""
        assert False

    @abstractmethod
    def read_discrete_inputs(self, unit, address, count):
        """Read discrete inputs."""
        assert False

    @abstractmethod
    def read_input_registers(self, unit, address, count):
        """Read input registers."""
        assert False

    @abstractmethod
    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        assert False

    @abstractmethod
    def write_coil(self, unit, address, value):
        """Write coil."""
        assert False

    @abstractmethod
    def write_register(self, unit, address, value):
        """Write register."""
        assert False

    @abstractmethod
    def write_registers(self, unit, address, values):
        """Write registers."""
        assert False

    def register_entity(
        self,
        name,
        slave,
        register,
        last_state,
        data_type=None,
        data_count=None,
        bit_mask=None,
    ):
        """Register the entity with the Modbus hub."""
