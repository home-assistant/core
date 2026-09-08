"""Helpers for the SolarEdge Modbus integration."""

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, Concatenate

from modbus_connection import ModbusSerialParams, ModbusTcpParams
from solaredged import SolarEdgeConnectionError, SolarEdgeError

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_BAUDRATE, DOMAIN, TYPE_SERIAL
from .entity import SolarEdgeModbusEntity


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data.

    The library's serial defaults are 8N1, which is what SolarEdge's RS485
    ports speak; only the baud rate is worth asking for.
    """
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def solaredge_exception_handler[_EntityT: SolarEdgeModbusEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate SolarEdge writes to serialize them and translate library errors.

    A successful write updates the library's decoded cache, so listeners are
    nudged to re-read entity state without waiting for the next poll.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            async with self.coordinator.config_entry.runtime_data.write_lock:
                await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except SolarEdgeConnectionError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(error)},
            ) from error

        except SolarEdgeError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rejected_value",
                translation_placeholders={"error": str(error)},
            ) from error

    return handler
