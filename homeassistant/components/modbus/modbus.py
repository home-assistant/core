"""Support for Modbus."""
import asyncio
from copy import deepcopy
import logging

from pymodbus.client.sync import ModbusSerialClient, ModbusTcpClient, ModbusUdpClient
from pymodbus.constants import Defaults
from pymodbus.exceptions import ModbusException
from pymodbus.transaction import ModbusRtuFramer

from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_call_later

from .const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_STATE,
    ATTR_UNIT,
    ATTR_VALUE,
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CLOSE_COMM_ON_ERROR,
    CONF_MSG_WAIT,
    CONF_PARITY,
    CONF_RETRIES,
    CONF_RETRY_ON_EMPTY,
    CONF_RTUOVERTCP,
    CONF_SERIAL,
    CONF_STOPBITS,
    CONF_TCP,
    CONF_UDP,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
    PLATFORMS,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)

ENTRY_FUNC = "func"
ENTRY_ATTR = "attr"
ENTRY_NAME = "name"

_LOGGER = logging.getLogger(__name__)

PYMODBUS_CALL = {
    CALL_TYPE_COIL: {
        ENTRY_ATTR: "bits",
        ENTRY_NAME: "read_coils",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_DISCRETE: {
        ENTRY_ATTR: "bits",
        ENTRY_NAME: "read_discrete_inputs",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_REGISTER_HOLDING: {
        ENTRY_ATTR: "registers",
        ENTRY_NAME: "read_holding_registers",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_REGISTER_INPUT: {
        ENTRY_ATTR: "registers",
        ENTRY_NAME: "read_input_registers",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_WRITE_COIL: {
        ENTRY_ATTR: "value",
        ENTRY_NAME: "write_coil",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_WRITE_COILS: {
        ENTRY_ATTR: "count",
        ENTRY_NAME: "write_coils",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_WRITE_REGISTER: {
        ENTRY_ATTR: "value",
        ENTRY_NAME: "write_register",
        ENTRY_FUNC: None,
    },
    CALL_TYPE_WRITE_REGISTERS: {
        ENTRY_ATTR: "count",
        ENTRY_NAME: "write_registers",
        ENTRY_FUNC: None,
    },
}


async def async_modbus_setup(
    hass, config, service_write_register_schema, service_write_coil_schema
):
    """Set up Modbus component."""

    hass.data[DOMAIN] = hub_collect = {}
    for conf_hub in config[DOMAIN]:
        my_hub = ModbusHub(hass, conf_hub)
        hub_collect[conf_hub[CONF_NAME]] = my_hub

        # modbus needs to be activated before components are loaded
        # to avoid a racing problem
        if not await my_hub.async_setup():
            return False

        # load platforms
        for component, conf_key in PLATFORMS:
            if conf_key in conf_hub:
                hass.async_create_task(
                    async_load_platform(hass, component, DOMAIN, conf_hub, config)
                )

    async def async_stop_modbus(event):
        """Stop Modbus service."""

        for client in hub_collect.values():
            await client.async_close()
            del client

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_modbus)

    async def async_write_register(service):
        """Write Modbus registers."""
        unit = int(float(service.data[ATTR_UNIT]))
        address = int(float(service.data[ATTR_ADDRESS]))
        value = service.data[ATTR_VALUE]
        client_name = (
            service.data[ATTR_HUB] if ATTR_HUB in service.data else DEFAULT_HUB
        )
        if isinstance(value, list):
            await hub_collect[client_name].async_pymodbus_call(
                unit, address, [int(float(i)) for i in value], CALL_TYPE_WRITE_REGISTERS
            )
        else:
            await hub_collect[client_name].async_pymodbus_call(
                unit, address, int(float(value)), CALL_TYPE_WRITE_REGISTER
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_REGISTER,
        async_write_register,
        schema=service_write_register_schema,
    )

    async def async_write_coil(service):
        """Write Modbus coil."""
        unit = service.data[ATTR_UNIT]
        address = service.data[ATTR_ADDRESS]
        state = service.data[ATTR_STATE]
        client_name = (
            service.data[ATTR_HUB] if ATTR_HUB in service.data else DEFAULT_HUB
        )
        if isinstance(state, list):
            await hub_collect[client_name].async_pymodbus_call(
                unit, address, state, CALL_TYPE_WRITE_COILS
            )
        else:
            await hub_collect[client_name].async_pymodbus_call(
                unit, address, state, CALL_TYPE_WRITE_COIL
            )

    hass.services.async_register(
        DOMAIN, SERVICE_WRITE_COIL, async_write_coil, schema=service_write_coil_schema
    )
    return True


class ModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(self, hass, client_config):
        """Initialize the Modbus hub."""

        # generic configuration
        self._client = None
        self._async_cancel_listener = None
        self._in_error = False
        self._lock = asyncio.Lock()
        self.hass = hass
        self._config_name = client_config[CONF_NAME]
        self._config_type = client_config[CONF_TYPE]
        self._config_delay = client_config[CONF_DELAY]
        self._pb_call = deepcopy(PYMODBUS_CALL)
        self._pb_class = {
            CONF_SERIAL: ModbusSerialClient,
            CONF_TCP: ModbusTcpClient,
            CONF_UDP: ModbusUdpClient,
            CONF_RTUOVERTCP: ModbusTcpClient,
        }
        self._pb_params = {
            "port": client_config[CONF_PORT],
            "timeout": client_config[CONF_TIMEOUT],
            "reset_socket": client_config[CONF_CLOSE_COMM_ON_ERROR],
            "retries": client_config[CONF_RETRIES],
            "retry_on_empty": client_config[CONF_RETRY_ON_EMPTY],
        }
        if self._config_type == CONF_SERIAL:
            # serial configuration
            self._pb_params.update(
                {
                    "method": client_config[CONF_METHOD],
                    "baudrate": client_config[CONF_BAUDRATE],
                    "stopbits": client_config[CONF_STOPBITS],
                    "bytesize": client_config[CONF_BYTESIZE],
                    "parity": client_config[CONF_PARITY],
                }
            )
        else:
            # network configuration
            self._pb_params["host"] = client_config[CONF_HOST]
            if self._config_type == CONF_RTUOVERTCP:
                self._pb_params["framer"] = ModbusRtuFramer

        Defaults.Timeout = client_config[CONF_TIMEOUT]
        if CONF_MSG_WAIT in client_config:
            self._msg_wait = client_config[CONF_MSG_WAIT] / 1000
        elif self._config_type == CONF_SERIAL:
            self._msg_wait = 30 / 1000
        else:
            self._msg_wait = 0

    def _log_error(self, text: str, error_state=True):
        log_text = f"Pymodbus: {text}"
        if self._in_error:
            _LOGGER.debug(log_text)
        else:
            _LOGGER.error(log_text)
            self._in_error = error_state

    async def async_setup(self):
        """Set up pymodbus client."""
        try:
            self._client = self._pb_class[self._config_type](**self._pb_params)
        except ModbusException as exception_error:
            self._log_error(str(exception_error), error_state=False)
            return False

        for entry in self._pb_call.values():
            entry[ENTRY_FUNC] = getattr(self._client, entry[ENTRY_NAME])

        await self.async_connect_task()
        return True

    async def async_connect_task(self):
        """Try to connect, and retry if needed."""
        async with self._lock:
            if not await self.hass.async_add_executor_job(self._pymodbus_connect):
                err = f"{self._config_name} connect failed, retry in pymodbus"
                self._log_error(err, error_state=False)
                return

        # Start counting down to allow modbus requests.
        if self._config_delay:
            self._async_cancel_listener = async_call_later(
                self.hass, self._config_delay, self.async_end_delay
            )

    @callback
    def async_end_delay(self, args):
        """End startup delay."""
        self._async_cancel_listener = None
        self._config_delay = 0

    def _pymodbus_close(self):
        """Close sync. pymodbus."""
        if self._client:
            try:
                self._client.close()
            except ModbusException as exception_error:
                self._log_error(str(exception_error))
        self._client = None

    async def async_close(self):
        """Disconnect client."""
        if self._async_cancel_listener:
            self._async_cancel_listener()
            self._async_cancel_listener = None

        async with self._lock:
            return await self.hass.async_add_executor_job(self._pymodbus_close)

    def _pymodbus_connect(self):
        """Connect client."""
        try:
            return self._client.connect()
        except ModbusException as exception_error:
            self._log_error(str(exception_error), error_state=False)
            return False

    def _pymodbus_call(self, unit, address, value, use_call):
        """Call sync. pymodbus."""
        kwargs = {"unit": unit} if unit else {}
        try:
            result = self._pb_call[use_call][ENTRY_FUNC](address, value, **kwargs)
        except ModbusException as exception_error:
            self._log_error(str(exception_error))
            return None
        if not hasattr(result, self._pb_call[use_call][ENTRY_ATTR]):
            self._log_error(str(result))
            return None
        self._in_error = False
        return result

    async def async_pymodbus_call(self, unit, address, value, use_call):
        """Convert async to sync pymodbus call."""
        if self._config_delay:
            return None
        if not self._client:
            return None
        async with self._lock:
            result = await self.hass.async_add_executor_job(
                self._pymodbus_call, unit, address, value, use_call
            )
            if self._msg_wait:
                # small delay until next request/response
                await asyncio.sleep(self._msg_wait)
            return result
