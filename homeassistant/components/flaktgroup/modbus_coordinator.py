"""Modbus Data Update Coordinator."""
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import logging
import math

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ModbusResponse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ModbusDatapointType(Enum):
    """Modbus Datapoint Type."""

    HOLDING_REGISTER = (1,)
    COIL = 2


@dataclass(frozen=True)
class ModbusDatapoint:
    """Modbus datapoint."""

    slave: int
    type: ModbusDatapointType
    address: int
    scale: float = 1


@dataclass(frozen=True)
class ModbusDatapointContext:
    """Modbus Datapoint Context."""

    modbus_datapoint: ModbusDatapoint | set[ModbusDatapoint]
    enabled: Callable[[], bool]

    def __eq__(self, other) -> bool:
        """Compare ModbusDatapointContext."""
        return (
            isinstance(other, ModbusDatapointContext)
            and self.modbus_datapoint == other.modbus_datapoint
        )


@dataclass
class ModbusDatapointDescriptionMixin:
    """SensorEntityDescription for Modbus-backed entities."""

    modbus_datapoint: ModbusDatapoint | None = None
    scale: float | int | None = None

    def from_modbus_value(self, number):
        """Apply scaling if needed."""
        scale = self.scale or 1
        actual_number = number * scale
        if scale < 1:
            decimals = -round(math.log10(scale))
            return round(actual_number, decimals)
        return round(actual_number)


class FlaktgroupModbusDataUpdateCoordinator(DataUpdateCoordinator):
    """Flaktgroup Modbus Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, name, host, port, update_interval_seconds
    ) -> None:
        """Init the Flaktgroup Modbus Data Update Coordinator."""
        if update_interval_seconds < 1:
            raise ConfigEntryNotReady

        super().__init__(
            hass,
            _LOGGER,
            name=f"{name} Update Coordinator",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

        self._client: AsyncModbusTcpClient = AsyncModbusTcpClient(host, port)

    async def async_connect(self) -> bool:
        """Connect to the Fläktgroup device modbus."""
        return await self._client.connect()

    async def _async_update_data(self) -> dict[ModbusDatapoint, int]:
        data = {}
        for async_context in self.async_contexts():
            if async_context.enabled():
                datapoints = async_context.modbus_datapoint
                if not isinstance(datapoints, Iterable):
                    datapoints = [datapoints]

                for datapoint in datapoints:
                    if datapoint not in data:
                        data[datapoint] = int(await self.read_datapoint(datapoint))

        return data

    async def write(self, datapoint: ModbusDatapoint, value: int) -> bool:
        """Immediately write a holding register."""
        try:
            if datapoint.type == ModbusDatapointType.HOLDING_REGISTER:
                result = await self._client.write_register(
                    datapoint.address, value, slave=datapoint.slave
                )  # type: ignore[misc] # need to ignore until a new version of pymodbus is released (see https://github.com/pymodbus-dev/pymodbus/pull/1842)
            elif datapoint.type == ModbusDatapointType.COIL:
                raise NotImplementedError
            else:
                raise NotImplementedError
        except ModbusException as exception_error:
            _LOGGER.error(
                "Error: pymodbus thrown an exception: %s", str(exception_error)
            )
            return False
        if not result:
            _LOGGER.error("Error: pymodbus returned None")
            return False
        if result.isError():
            _LOGGER.error("Error: pymodbus returned isError True")
            return False
        return True

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        _LOGGER.warning("Closing modbus `%s` communication", self.name)
        self._client.close()
        _LOGGER.warning("Modbus `%s` communication closed", self.name)

    async def read_datapoint(self, datapoint: ModbusDatapoint):
        """Read datapoint from a holding register or a coil."""
        if datapoint.type == ModbusDatapointType.HOLDING_REGISTER:
            return await self._get_int_holding_register(
                datapoint.slave, datapoint.address
            )
        if datapoint.type == ModbusDatapointType.COIL:
            return await self._get_int_coil(datapoint.slave, datapoint.address)
        raise NotImplementedError

    async def _get_int_holding_register(self, slave, address):
        try:
            result: ModbusResponse = await self._client.read_holding_registers(
                address=address, slave=slave
            )
        except ModbusException as exception_error:
            _LOGGER.error(
                "Error: pymodbus thrown an exception: %s", str(exception_error)
            )
            return None
        if not result:
            self._log_error("Error: pymodbus returned None")
            return None
        if result.isError():
            self._log_error("Error: pymodbus returned isError True")
            return None
        return int(
            ModbusClientMixin.convert_from_registers(
                result.registers, ModbusClientMixin.DATATYPE.INT16
            )
        )

    async def _get_int_coil(self, slave, address):
        try:
            result: ModbusResponse = await self._client.read_coils(
                address=address, slave=slave
            )
        except ModbusException as exception_error:
            _LOGGER.error(
                "Error: pymodbus thrown an exception: %s", str(exception_error)
            )
            return None
        if not result:
            self._log_error("Error: pymodbus returned None")
            return None
        if result.isError():
            self._log_error("Error: pymodbus returned isError True")
            return None
        return bool(result.bits[0] & 1)
