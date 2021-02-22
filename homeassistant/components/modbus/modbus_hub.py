from abc import ABC, abstractmethod
import logging
import threading

from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient, ModbusUdpClient
from pymodbus.transaction import ModbusRtuFramer

from pymodbus.server.asyncio import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.exceptions import ConnectionException

from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STARTED,
)

from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers import entity_registry

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
    DATA_TYPE_STRING,
)
from .const import (
    CONF_TYPE_SERIAL,
    CONF_TYPE_RTUOVERTCP,
    CONF_TYPE_TCP,
    CONF_TYPE_TCPSERVER,
    CONF_TYPE_UDP,
)

_LOGGER = logging.getLogger(__name__)


class AbstractModbusHub(ABC):
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
        pass


class ModbusClientHub(AbstractModbusHub):
    """ModbusClientHub implement AbstractModbusHub and represent all client type configurations """

    def __init__(self, client_config):
        """Initialize the Modbus client hub."""
        super().__init__(client_config)

        if self._config_type == "serial":
            # serial configuration
            self._config_method = client_config[CONF_METHOD]
            self._config_baudrate = client_config[CONF_BAUDRATE]
            self._config_stopbits = client_config[CONF_STOPBITS]
            self._config_bytesize = client_config[CONF_BYTESIZE]
            self._config_parity = client_config[CONF_PARITY]
        else:
            # network configuration
            self._config_host = client_config[CONF_HOST]
            self._config_delay = client_config[CONF_DELAY]
            if self._config_delay > 0:
                _LOGGER.warning(
                    "Parameter delay is accepted but not used in this version"
                )

    def setup(self):
        """Set up pymodbus client."""
        if self._config_type == "serial":
            self._client = ModbusSerialClient(
                method=self._config_method,
                port=self._config_port,
                baudrate=self._config_baudrate,
                stopbits=self._config_stopbits,
                bytesize=self._config_bytesize,
                parity=self._config_parity,
                timeout=self._config_timeout,
                retry_on_empty=True,
            )
        elif self._config_type == "rtuovertcp":
            self._client = ModbusTcpClient(
                host=self._config_host,
                port=self._config_port,
                framer=ModbusRtuFramer,
                timeout=self._config_timeout,
            )
        elif self._config_type == "tcp":
            self._client = ModbusTcpClient(
                host=self._config_host,
                port=self._config_port,
                timeout=self._config_timeout,
            )
        elif self._config_type == "udp":
            self._client = ModbusUdpClient(
                host=self._config_host,
                port=self._config_port,
                timeout=self._config_timeout,
            )
        else:
            assert False

        # Connect device
        self.connect()

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def connect(self):
        """Connect client."""
        with self._lock:
            if self._client:
                self._client.connect()

    def read_coils(self, unit, address, count):
        """Read coils."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_coils(address, count, **kwargs)

    def read_discrete_inputs(self, unit, address, count):
        """Read discrete inputs."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_discrete_inputs(address, count, **kwargs)

    def read_input_registers(self, unit, address, count):
        """Read input registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_input_registers(address, count, **kwargs)

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            return self._client.read_holding_registers(address, count, **kwargs)

    def write_coil(self, unit, address, value):
        """Write coil."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_coil(address, value, **kwargs)

    def write_register(self, unit, address, value):
        """Write register."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_register(address, value, **kwargs)

    def write_registers(self, unit, address, values):
        """Write registers."""
        with self._lock:
            kwargs = {"unit": unit} if unit else {}
            self._client.write_registers(address, values, **kwargs)
