"""Support for Modbus."""

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from modbus_connection import ModbusConnection, ModbusError
from modbus_connection.pymodbus import PymodbusConnection
from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient,
    AsyncModbusUdpClient,
)
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType
import voluptuous as vol

from homeassistant.const import (
    ATTR_STATE,
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    _LOGGER,
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_SLAVE,
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
    CONF_MSG_WAIT,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_HUB,
    DOMAIN,
    PLATFORMS,
    RTUOVERTCP,
    SERIAL,
    SERVICE_STOP,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
    SIGNAL_STOP_ENTITY,
    TCP,
    UDP,
)
from .validators import check_config

DATA_MODBUS_HUBS: HassKey[dict[str, ModbusHub]] = HassKey(DOMAIN)

PRIMARY_RECONNECT_DELAY = 60


@dataclass
class ModbusResult:
    """Result of a Modbus read or write call.

    Reads populate exactly one of ``bits`` (coils/discrete inputs) or
    ``registers`` (holding/input registers); writes leave both unset and the
    non-``None`` instance simply signals success.
    """

    bits: list[bool] | None = None
    registers: list[int] | None = None


async def async_modbus_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    """Set up Modbus component."""

    if config[DOMAIN]:
        config[DOMAIN] = check_config(hass, config[DOMAIN])
        if not config[DOMAIN]:
            return False
    if DATA_MODBUS_HUBS in hass.data and config[DOMAIN] == []:
        hubs = hass.data[DATA_MODBUS_HUBS]
        for hub in hubs.values():
            if not await hub.async_setup():
                return False
        hub_collect = hass.data[DATA_MODBUS_HUBS]
    else:
        hass.data[DATA_MODBUS_HUBS] = hub_collect = {}

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

    async def async_stop_modbus(event: Event) -> None:
        """Stop Modbus service."""
        for client in hub_collect.values():
            await client.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_modbus)

    def _get_service_call_details(
        service: ServiceCall,
    ) -> tuple[ModbusHub, int, int]:
        """Return the details required to process the service call."""
        device_address = service.data.get(ATTR_SLAVE, service.data.get(ATTR_UNIT, 1))
        address = service.data[ATTR_ADDRESS]
        hub = hub_collect[service.data[ATTR_HUB]]
        return (hub, device_address, address)

    async def async_write_register(service: ServiceCall) -> None:
        """Write Modbus registers."""
        hub, device_address, address = _get_service_call_details(service)

        value = service.data[ATTR_VALUE]
        if isinstance(value, list):
            await hub.async_pb_call(
                device_address, address, value, CALL_TYPE_WRITE_REGISTERS
            )
        else:
            await hub.async_pb_call(
                device_address, address, value, CALL_TYPE_WRITE_REGISTER
            )

    async def async_write_coil(service: ServiceCall) -> None:
        """Write Modbus coil."""
        hub, device_address, address = _get_service_call_details(service)

        state = service.data[ATTR_STATE]

        if isinstance(state, list):
            await hub.async_pb_call(
                device_address, address, state, CALL_TYPE_WRITE_COILS
            )
        else:
            await hub.async_pb_call(
                device_address, address, state, CALL_TYPE_WRITE_COIL
            )

    for x_write in (
        (SERVICE_WRITE_REGISTER, async_write_register, ATTR_VALUE, cv.positive_int),
        (SERVICE_WRITE_COIL, async_write_coil, ATTR_STATE, cv.boolean),
    ):
        hass.services.async_register(
            DOMAIN,
            x_write[0],
            x_write[1],
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_HUB, default=DEFAULT_HUB): cv.string,
                    vol.Exclusive(ATTR_SLAVE, "unit"): cv.positive_int,
                    vol.Exclusive(ATTR_UNIT, "unit"): cv.positive_int,
                    vol.Required(ATTR_ADDRESS): cv.positive_int,
                    vol.Required(x_write[2]): vol.Any(
                        cv.positive_int, vol.All(cv.ensure_list, [x_write[3]])
                    ),
                }
            ),
        )

    async def async_stop_hub(service: ServiceCall) -> None:
        """Stop Modbus hub."""
        async_dispatcher_send(hass, SIGNAL_STOP_ENTITY)
        hub = hub_collect[service.data[ATTR_HUB]]
        await hub.async_close()

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP,
        async_stop_hub,
        schema=vol.Schema({vol.Required(ATTR_HUB): cv.string}),
    )
    return True


class ModbusHub:
    """Thread safe wrapper class for modbus_connection."""

    def __init__(self, hass: HomeAssistant, client_config: dict[str, Any]) -> None:
        """Initialize the Modbus hub."""

        # generic configuration
        self._client: (
            AsyncModbusSerialClient | AsyncModbusTcpClient | AsyncModbusUdpClient | None
        ) = None
        self._connection: ModbusConnection | None = None
        self._lock = asyncio.Lock()
        self.event_connected = asyncio.Event()
        self.hass = hass
        self.name = client_config[CONF_NAME]
        self._config_type = client_config[CONF_TYPE]
        self.config_delay = client_config[CONF_DELAY]
        self._connect_task: asyncio.Task
        self._last_log_error: str = ""
        self._pb_class = {
            SERIAL: AsyncModbusSerialClient,
            TCP: AsyncModbusTcpClient,
            UDP: AsyncModbusUdpClient,
            RTUOVERTCP: AsyncModbusTcpClient,
        }
        self._pb_params = {
            "port": client_config[CONF_PORT],
            "timeout": client_config[CONF_TIMEOUT],
            "retries": 3,
        }
        if self._config_type == SERIAL:
            # serial configuration
            if client_config[CONF_METHOD] == "ascii":
                self._pb_params["framer"] = FramerType.ASCII
            else:
                self._pb_params["framer"] = FramerType.RTU
            self._pb_params.update(
                {
                    "baudrate": client_config[CONF_BAUDRATE],
                    "stopbits": client_config[CONF_STOPBITS],
                    "bytesize": client_config[CONF_BYTESIZE],
                    "parity": client_config[CONF_PARITY],
                }
            )
        else:
            # network configuration
            self._pb_params["host"] = client_config[CONF_HOST]
            if self._config_type == RTUOVERTCP:
                self._pb_params["framer"] = FramerType.RTU
            else:
                self._pb_params["framer"] = FramerType.SOCKET

        if CONF_MSG_WAIT in client_config:
            self._msg_wait = client_config[CONF_MSG_WAIT] / 1000
        elif self._config_type == SERIAL:
            self._msg_wait = 30 / 1000
        else:
            self._msg_wait = 0

    def _log_error(self, text: str) -> None:
        if text == self._last_log_error:
            return
        self._last_log_error = text
        log_text = f"Pymodbus: {self.name}: {text}"
        _LOGGER.error(log_text)

    async def async_pb_connect(self) -> None:
        """Connect to device, async."""
        while True:
            try:
                if await self._client.connect():  # type: ignore[union-attr]
                    _LOGGER.info(f"modbus {self.name} communication open")
                    break
            except ModbusException as exception_error:
                self._log_error(
                    f"{self.name} connect failed, please check"
                    f" your configuration ({exception_error!s})"
                )
            _LOGGER.info(
                f"modbus {self.name} connect NOT a success !"
                f" retrying in {PRIMARY_RECONNECT_DELAY} seconds"
            )
            await asyncio.sleep(PRIMARY_RECONNECT_DELAY)

        if self.config_delay:
            await asyncio.sleep(self.config_delay)
        self.config_delay = 0
        self.event_connected.set()

    async def async_setup(self) -> bool:
        """Set up pymodbus client."""
        try:
            self._client = self._pb_class[self._config_type](**self._pb_params)
        except ModbusException as exception_error:
            self._log_error(str(exception_error))
            return False
        self._connection = PymodbusConnection(self._client)

        self._connect_task = self.hass.async_create_background_task(
            self.async_pb_connect(), "modbus-connect"
        )
        return True

    async def async_restart(self) -> None:
        """Reconnect client."""
        if self._client:
            await self.async_close()

        await self.async_setup()

    async def async_close(self) -> None:
        """Disconnect client."""
        self.event_connected.set()
        if not self._connect_task.done():
            self._connect_task.cancel()

        if self._client:
            try:
                self._client.close()
            except ModbusException as exception_error:
                self._log_error(str(exception_error))
            self._client = None
            self._connection = None
            _LOGGER.info(f"modbus {self.name} communication closed")

    async def low_level_pb_call(
        self, slave: int | None, address: int, value: int | list[int], use_call: str
    ) -> ModbusResult | None:
        """Call modbus_connection, mapping errors onto a None result."""
        unit = self._connection.for_unit(slave if slave is not None else 1)  # type: ignore[union-attr]
        try:
            if use_call == CALL_TYPE_COIL:
                return ModbusResult(
                    bits=await unit.read_coils(address, cast(int, value))
                )
            if use_call == CALL_TYPE_DISCRETE:
                return ModbusResult(
                    bits=await unit.read_discrete_inputs(address, cast(int, value))
                )
            if use_call == CALL_TYPE_REGISTER_HOLDING:
                return ModbusResult(
                    registers=await unit.read_holding_registers(
                        address, cast(int, value)
                    )
                )
            if use_call == CALL_TYPE_REGISTER_INPUT:
                return ModbusResult(
                    registers=await unit.read_input_registers(address, cast(int, value))
                )
            if use_call == CALL_TYPE_WRITE_COIL:
                await unit.write_coil(address, bool(value))
            elif use_call == CALL_TYPE_WRITE_COILS:
                values = value if isinstance(value, list) else [value]
                await unit.write_coils(address, [bool(v) for v in values])
            elif use_call == CALL_TYPE_WRITE_REGISTER:
                await unit.write_register(address, cast(int, value))
            elif use_call == CALL_TYPE_WRITE_REGISTERS:
                values = value if isinstance(value, list) else [value]
                await unit.write_registers(address, values)
        except ModbusError as exception_error:
            error = f"Error: device: {slave} address: {address} -> {exception_error!s}"
            self._log_error(error)
            return None
        return ModbusResult()

    async def async_pb_call(
        self,
        unit: int | None,
        address: int,
        value: int | list[int],
        use_call: str,
    ) -> ModbusResult | None:
        """Serialize a single Modbus request/response cycle."""
        if not self._connection:
            return None
        async with self._lock:
            result = await self.low_level_pb_call(unit, address, value, use_call)
            if self._msg_wait:
                # small delay until next request/response
                await asyncio.sleep(self._msg_wait)
            return result
