"""Modbus server implementation."""
import ctypes
import logging

from pymodbus.constants import Endian
from pymodbus.datastore import (
    ModbusServerContext,
    ModbusSlaveContext,
    ModbusSparseDataBlock,
)
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.server.asyncio import StartTcpServer

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_ON

from .const import DATA_TYPE_FLOAT, DATA_TYPE_INT, DATA_TYPE_STRING, DATA_TYPE_UINT
from .modbus_base import BaseModbusHub

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


class ModbusServerHub(BaseModbusHub):
    """ModbusServerHub acts as a modbus slave."""

    def __init__(self, client_config, hass):
        """Initialize the Modbus server hub."""
        super().__init__(client_config)

        self._entities = []
        # network configuration
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
            if bit_mask > 0:
                entity["bit_mask"] = bit_mask
        else:
            builder = BinaryPayloadBuilder(byteorder=Endian.Big)
            if last_state == "unavailable":
                last_state = None
            if data_type == DATA_TYPE_FLOAT:
                if data_count == 4:
                    builder.add_32bit_float(float(last_state or 0.0))
                else:
                    builder.add_16bit_float(float(last_state or 0.0))
            elif data_type == DATA_TYPE_INT:
                if data_count == 4:
                    builder.add_32bit_int(int(last_state or 0))
                else:
                    builder.add_16bit_int(int(last_state or 0))
            elif data_type == DATA_TYPE_UINT:
                if data_count == 4:
                    builder.add_32bit_uint(ctypes.c_uint(int(last_state or 0)).value)
                else:
                    builder.add_16bit_uint(ctypes.c_ushort(int(last_state or 0)).value)
            elif data_type == DATA_TYPE_STRING:
                builder.add_string(last_state or (" " * data_count))
            entity = {
                "name": name,
                "unit": unit,
                "register": register,
                "data": builder.to_registers(),
            }

        self._entities.append(entity)

    def _build_server_blocks(self, entities):

        assoc_array = {}
        for entity in entities:
            register = int(entity["register"])
            unit_address = int(entity["unit"])
            assoc_array[unit_address] = server_registers = assoc_array.get(
                unit_address, {}
            )
            if "bit_mask" in entity:
                bit_mask = int(entity["bit_mask"])
                # value_data represent a turned on bits in the result register if state is ON
                value_data = bit_mask if entity["data"][0] else 0
                if register in server_registers:
                    # mask holds the used positions, value holds combined bit mask for the slave
                    value, mask = server_registers[register]
                    if mask & bit_mask > 0:
                        _LOGGER.error(
                            "Modbus slave entity %s register %d bit mask %d overlaps with the already registered entities",
                            entity["name"],
                            server_registers[register],
                            bit_mask,
                        )
                        assert False
                    # update resulting register value and used bits mask
                    server_registers[register] = [value | value_data, mask | bit_mask]
                else:
                    server_registers[register] = [value_data, bit_mask]
            else:
                for item in entity["data"]:
                    if register in server_registers:
                        _LOGGER.error(
                            "Modbus slave entity %s register %d overlaps with the already registered entities",
                            entity["name"],
                            server_registers[register],
                        )
                        assert False
                    server_registers[register] = item
                    register = register + 1

        def _strip_bit_maks(registers):
            result = {}
            for register in registers:
                item = registers[register]
                result[register] = item[0] if isinstance(item, list) else item
            return result

        return {
            unit_address: ModbusSparseDataBlock(
                _strip_bit_maks(assoc_array[unit_address])
            )
            for unit_address in assoc_array
        }

    async def start_server(self, _):
        """Start modbus slave."""
        with self._lock:
            self._block = self._build_server_blocks(self._entities)

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
            address=("0.0.0.0", self._config_port),
            allow_reuse_address=True,
            defer_start=True,
        )

        await self._server.serve_forever()
