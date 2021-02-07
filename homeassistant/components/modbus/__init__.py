"""Support for Modbus."""
import logging
import threading

from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient, ModbusUdpClient
from pymodbus.transaction import ModbusRtuFramer
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.const import (
    ATTR_STATE,
    CONF_COVERS,
    CONF_DELAY,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_UNIT,
    ATTR_VALUE,
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CLIMATES,
    CONF_CURRENT_TEMP,
    CONF_CURRENT_TEMP_REGISTER_TYPE,
    CONF_DATA_COUNT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PARITY,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_SCALE,
    CONF_STATE_CLOSED,
    CONF_STATE_CLOSING,
    CONF_STATE_OPEN,
    CONF_STATE_OPENING,
    CONF_STATUS_REGISTER,
    CONF_STATUS_REGISTER_TYPE,
    CONF_STEP,
    CONF_STOPBITS,
    CONF_TARGET_TEMP,
    CONF_UNIT,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DEFAULT_STRUCTURE_PREFIX,
    DEFAULT_TEMP_UNIT,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME, default=DEFAULT_HUB): cv.string})

CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CURRENT_TEMP): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLAVE): cv.positive_int,
        vol.Required(CONF_TARGET_TEMP): cv.positive_int,
        vol.Optional(CONF_DATA_COUNT, default=2): cv.positive_int,
        vol.Optional(
            CONF_CURRENT_TEMP_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING
        ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_FLOAT): vol.In(
            [DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT, DATA_TYPE_CUSTOM]
        ),
        vol.Optional(CONF_PRECISION, default=1): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.time_period, lambda value: value.total_seconds()
        ),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=35): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP, default=5): cv.positive_int,
        vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
        vol.Optional(CONF_STRUCTURE, default=DEFAULT_STRUCTURE_PREFIX): cv.string,
        vol.Optional(CONF_UNIT, default=DEFAULT_TEMP_UNIT): cv.string,
    }
)

COVERS_SCHEMA = vol.All(
    cv.has_at_least_one_key(CALL_TYPE_COIL, CONF_REGISTER),
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                cv.time_period, lambda value: value.total_seconds()
            ),
            vol.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): cv.positive_int,
            vol.Optional(CONF_STATE_CLOSED, default=0): cv.positive_int,
            vol.Optional(CONF_STATE_CLOSING, default=3): cv.positive_int,
            vol.Optional(CONF_STATE_OPEN, default=1): cv.positive_int,
            vol.Optional(CONF_STATE_OPENING, default=2): cv.positive_int,
            vol.Optional(CONF_STATUS_REGISTER): cv.positive_int,
            vol.Optional(
                CONF_STATUS_REGISTER_TYPE,
                default=CALL_TYPE_REGISTER_HOLDING,
            ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
            vol.Exclusive(CALL_TYPE_COIL, CONF_INPUT_TYPE): cv.positive_int,
            vol.Exclusive(CONF_REGISTER, CONF_INPUT_TYPE): cv.positive_int,
        }
    ),
)

SERIAL_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_BAUDRATE): cv.positive_int,
        vol.Required(CONF_BYTESIZE): vol.Any(5, 6, 7, 8),
        vol.Required(CONF_METHOD): vol.Any("rtu", "ascii"),
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_PARITY): vol.Any("E", "O", "N"),
        vol.Required(CONF_STOPBITS): vol.Any(1, 2),
        vol.Required(CONF_TYPE): "serial",
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        vol.Optional(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATE_SCHEMA]),
        vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
    }
)

ETHERNET_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_TYPE): vol.Any("tcp", "udp", "rtuovertcp"),
        vol.Optional(CONF_TIMEOUT, default=3): cv.socket_timeout,
        vol.Optional(CONF_DELAY, default=0): cv.positive_int,
        vol.Optional(CONF_CLIMATES): vol.All(cv.ensure_list, [CLIMATE_SCHEMA]),
        vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
    }
)

SERVICE_WRITE_REGISTER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Any(
            cv.positive_int, vol.All(cv.ensure_list, [cv.positive_int])
        ),
    }
)

SERVICE_WRITE_COIL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(ATTR_UNIT): cv.positive_int,
        vol.Required(ATTR_ADDRESS): cv.positive_int,
        vol.Required(ATTR_STATE): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Any(SERIAL_SCHEMA, ETHERNET_SCHEMA),
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up Modbus component."""
    hass.data[DOMAIN] = hub_collect = {}

    for conf_hub in config[DOMAIN]:
        hub_collect[conf_hub[CONF_NAME]] = ModbusHub(conf_hub)

        # load platforms
        for component, conf_key in (
            ("climate", CONF_CLIMATES),
            ("cover", CONF_COVERS),
        ):
            if conf_key in conf_hub:
                load_platform(hass, component, DOMAIN, conf_hub, config)

    def stop_modbus(event):
        """Stop Modbus service."""
        for client in hub_collect.values():
            client.close()

    def write_register(service):
        """Write Modbus registers."""
        unit = int(float(service.data[ATTR_UNIT]))
        address = int(float(service.data[ATTR_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = service.data[ATTR_HUB]
        if isinstance(value, list):
            hub_collect[client_name].write_registers(
                unit, address, [int(float(i)) for i in value]
            )
        else:
            hub_collect[client_name].write_register(unit, address, int(float(value)))

    def write_coil(service):
        """Write Modbus coil."""
        unit = service.data[ATTR_UNIT]
        address = service.data[ATTR_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = service.data[ATTR_HUB]
        hub_collect[client_name].write_coil(unit, address, state)

    # do not wait for EVENT_HOMEASSISTANT_START, activate pymodbus now
    for client in hub_collect.values():
        client.setup()

    # register function to gracefully stop modbus
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_modbus)

    # Register services for modbus
    hass.services.register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        write_register,
        schema=SERVICE_WRITE_REGISTER_SCHEMA,
    )
    hass.services.register(
        DOMAIN, SERVICE_WRITE_COIL, write_coil, schema=SERVICE_WRITE_COIL_SCHEMA
    )
    return True


class ModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, client_config):
        """Initialize the Modbus hub."""
        # generic configuration
        self._client = None
        self._lock = threading.Lock()
        self._config_name = client_config[CONF_NAME]
        self._config_type = client_config[CONF_TYPE]
        self._config_port = client_config[CONF_PORT]
        self._config_timeout = client_config[CONF_TIMEOUT]
        self._config_delay = 0

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

    @property
    def name(self):
        """Return the name of this hub."""
        return self._config_name

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
