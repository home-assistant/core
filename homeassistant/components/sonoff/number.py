from homeassistant.components.number import NumberEntity
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore

# https://github.com/home-assistant/core/blob/2022.7.0/homeassistant/components/number/__init__.py
BACKWARD = {
    "_attr_max_value": "_attr_native_max_value",
    "_attr_min_value": "_attr_native_min_value",
    "_attr_step": "_attr_native_step",
    "_attr_value": "_attr_native_value",
    "async_set_value": "async_set_native_value",
}


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, NumberEntity)])
    )


# noinspection PyAbstractClass
class XNumber(XEntity, NumberEntity):
    """
    customizable number entity for simple 'params'
    """
    multiply: float = None
    round: int = None

    def set_state(self, params: dict):
        value = params[self.param]
        if self.multiply:
            value *= self.multiply
        if self.round is not None:
            # convert to int when round is zero
            value = round(value, self.round or None)
        self._attr_native_value = value

    async def async_set_native_value(self, value: float) -> None:
        if self.multiply:
            value /= self.multiply
        await self.ewelink.send(self.device, {self.param: int(value)})

    # backward compatibility fix
    if (MAJOR_VERSION, MINOR_VERSION) < (2022, 7):
        # fix Hass v2021.12 empty attribute bug
        _attr_native_value = None

        def __getattribute__(self, name: str):
            name = BACKWARD.get(name, name)
            return super().__getattribute__(name)


class XPulseWidth(XNumber):
    _attr_native_max_value = 36000
    _attr_native_min_value = 0.5
    _attr_native_step = 0.5

    def set_state(self, params: dict):
        self._attr_native_value = params["pulseWidth"] / 1000

    async def async_set_native_value(self, value: float) -> None:
        """
        we need to send {'pulse': 'on'}  in order to also set the pilseWidth
        else it'll reject the command
        also, since value is in (float) seconds, ensure we send milliseconds
        in 500 multiples (int(value / .5) * 500)
        """
        await self.ewelink.send(
            self.device, {"pulse": "on", "pulseWidth": int(value / .5) * 500}
        )
