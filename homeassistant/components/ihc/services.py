"""Support for IHC services."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, IHC_CONTROLLER, IHC_CONTROLLER_INDEX
from .util import async_pulse, async_set_bool, async_set_float, async_set_int


class IhcService(StrEnum):
    """Store keys for IHC services."""

    SET_RUNTIME_VALUE_BOOL = "set_runtime_value_bool"
    SET_RUNTIME_VALUE_INT = "set_runtime_value_int"
    SET_RUNTIME_VALUE_FLOAT = "set_runtime_value_float"
    PULSE = "pulse"


class IhcServiceArgument(StrEnum):
    """Store keys for IHC service arguments."""

    CONTROLLER_ID = "controller_id"
    IHC_ID = "ihc_id"
    VALUE = "value"


SET_RUNTIME_VALUE_BOOL_SCHEMA = probatio.Schema(
    {
        probatio.Required(IhcServiceArgument.IHC_ID): cv.positive_int,
        probatio.Required(IhcServiceArgument.VALUE): cv.boolean,
        probatio.Optional(IhcServiceArgument.CONTROLLER_ID, default=0): cv.positive_int,
    }
)

SET_RUNTIME_VALUE_INT_SCHEMA = probatio.Schema(
    {
        probatio.Required(IhcServiceArgument.IHC_ID): cv.positive_int,
        probatio.Required(IhcServiceArgument.VALUE): probatio.Coerce(int),
        probatio.Optional(IhcServiceArgument.CONTROLLER_ID, default=0): cv.positive_int,
    }
)

SET_RUNTIME_VALUE_FLOAT_SCHEMA = probatio.Schema(
    {
        probatio.Required(IhcServiceArgument.IHC_ID): cv.positive_int,
        probatio.Required(IhcServiceArgument.VALUE): probatio.Coerce(float),
        probatio.Optional(IhcServiceArgument.CONTROLLER_ID, default=0): cv.positive_int,
    }
)

PULSE_SCHEMA = probatio.Schema(
    {
        probatio.Required(IhcServiceArgument.IHC_ID): cv.positive_int,
        probatio.Optional(IhcServiceArgument.CONTROLLER_ID, default=0): cv.positive_int,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Register the IHC services."""

    def _get_controller(call):
        controller_index = call.data[IhcServiceArgument.CONTROLLER_ID]
        for controller_id in hass.data[DOMAIN]:
            controller_conf = hass.data[DOMAIN][controller_id]
            if controller_conf[IHC_CONTROLLER_INDEX] == controller_index:
                return controller_conf[IHC_CONTROLLER]
        # if not found the controller_index is ouf of range
        raise ValueError("The controller index is out of range")

    async def async_set_runtime_value_bool(call):
        """Set a IHC runtime bool value service function."""
        ihc_id = call.data[IhcServiceArgument.IHC_ID]
        value = call.data[IhcServiceArgument.VALUE]
        ihc_controller = _get_controller(call)
        await async_set_bool(hass, ihc_controller, ihc_id, value)

    async def async_set_runtime_value_int(call):
        """Set a IHC runtime integer value service function."""
        ihc_id = call.data[IhcServiceArgument.IHC_ID]
        value = call.data[IhcServiceArgument.VALUE]
        ihc_controller = _get_controller(call)
        await async_set_int(hass, ihc_controller, ihc_id, value)

    async def async_set_runtime_value_float(call):
        """Set a IHC runtime float value service function."""
        ihc_id = call.data[IhcServiceArgument.IHC_ID]
        value = call.data[IhcServiceArgument.VALUE]
        ihc_controller = _get_controller(call)
        await async_set_float(hass, ihc_controller, ihc_id, value)

    async def async_pulse_runtime_input(call):
        """Pulse a IHC controller input function."""
        ihc_id = call.data[IhcServiceArgument.IHC_ID]
        ihc_controller = _get_controller(call)
        await async_pulse(hass, ihc_controller, ihc_id)

    hass.services.register(
        DOMAIN,
        IhcService.SET_RUNTIME_VALUE_BOOL,
        async_set_runtime_value_bool,
        schema=SET_RUNTIME_VALUE_BOOL_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        IhcService.SET_RUNTIME_VALUE_INT,
        async_set_runtime_value_int,
        schema=SET_RUNTIME_VALUE_INT_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        IhcService.SET_RUNTIME_VALUE_FLOAT,
        async_set_runtime_value_float,
        schema=SET_RUNTIME_VALUE_FLOAT_SCHEMA,
    )
    hass.services.register(
        DOMAIN, IhcService.PULSE, async_pulse_runtime_input, schema=PULSE_SCHEMA
    )
