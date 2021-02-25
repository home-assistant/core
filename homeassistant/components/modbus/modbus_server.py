"""Modbus server implementation."""
import logging

from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.exceptions import ConnectionException
from pymodbus.server.asyncio import StartTcpServer

from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED, STATE_ON

from .modbus_base import BaseModbusHub
from .utils import build_registers, build_server_blocks

_LOGGER = logging.getLogger(__name__)


class RegisterResult:
    """Modbus register wrapper."""

    def __init__(self, registers=[0]):
        """Initialize with the defaults."""
        self._registers = registers

    @property
    def registers(self):
        """Get registers."""
        return self._registers

    @property
    def bits(self):
        """Get bits."""
        return self._registers


class ModbusServerHub(BaseModbusHub):
    """ModbusServerHub acts as a modbus slave."""

    def __init__(self, client_config, hass):
        """Initialize the Modbus server hub."""
        super().__init__(client_config)

        self._entities = []
        # network configuration
        self._config_host = client_config.get(CONF_HOST, "0.0.0.0")
        self._server = None
        self._block = None

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.start_server)

    def setup(self):
        """No op for the server."""
        pass

    def close(self):
        """Shutdown server."""
        with self._lock:
            if self._server is not None:
                self._server.server_close()
                self._server = None

    def read_coils(self, unit, address, count):
        """Read coils."""
        self._ensure_connected()
        with self._lock:
            return RegisterResult(self._block[unit].getValues(address, count))

    def read_discrete_inputs(self, unit, address, count):
        """Read discrete inputs."""
        self._ensure_connected()
        with self._lock:
            return RegisterResult(self._block[unit].getValues(address, count))

    def read_input_registers(self, unit, address, count):
        """Read input registers."""
        self._ensure_connected()
        with self._lock:
            return RegisterResult(self._block[unit].getValues(address, count))

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        self._ensure_connected()
        with self._lock:
            return RegisterResult(self._block[unit].getValues(address, count))

    def write_coil(self, unit, address, value):
        """Write coil."""
        self._ensure_connected()
        with self._lock:
            self._block[unit].setValues(address, [value])

    def write_register(self, unit, address, value):
        """Write register."""
        self._ensure_connected()
        with self._lock:
            self._block[unit].setValues(address, [value])

    def write_registers(self, unit, address, values):
        """Write registers."""
        self._ensure_connected()
        with self._lock:
            self._block[unit].setValues(address, values)

    def _ensure_connected(self):
        if self._block is None:
            raise ConnectionException()
        if self._server and len(self._server.active_connections) == 0:
            raise ConnectionException()

    def register_entity(
        self,
        name,
        unit,
        register,
        last_state,
        data_type=None,
        data_count=None,
        bit_mask=None,
    ):
        """Register an entity with the Modbus server."""
        if data_type is None:
            data = 1 if last_state == STATE_ON else 0
            entity = {"name": name, "unit": unit, "register": register, "data": [data]}
            if bit_mask is not None and bit_mask > 0:
                entity["bit_mask"] = bit_mask
        else:
            entity = {
                "name": name,
                "unit": unit,
                "register": register,
                "data": build_registers(last_state, data_type, data_count),
            }

        self._entities.append(entity)

    async def start_server(self, _):
        """Start modbus slave."""
        with self._lock:
            self._block = build_server_blocks(self._entities)

        if self._block is None:
            return

        slaves = {
            unit: ModbusSlaveContext(
                di=self._block[unit],
                co=self._block[unit],
                hr=self._block[unit],
                ir=self._block[unit],
            )
            for unit in self._block
        }

        context = ModbusServerContext(slaves=slaves, single=False)

        self._server = await StartTcpServer(
            context,
            address=(self._config_host, self._config_port),
            allow_reuse_address=True,
            defer_start=True,
        )

        await self._server.serve_forever()
