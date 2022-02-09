import logging

from gehomesdk import ErdCodeType
from homeassistant.components.switch import SwitchEntity

from ...devices import ApplianceApi
from .ge_erd_binary_sensor import GeErdBinarySensor
from .bool_converter import BoolConverter

_LOGGER = logging.getLogger(__name__)

class GeErdSwitch(GeErdBinarySensor, SwitchEntity):
    """Switches for boolean ERD codes."""
    device_class = "switch"

    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType, bool_converter: BoolConverter = BoolConverter(), erd_override: str = None, icon_on_override: str = None, icon_off_override: str = None, device_class_override: str = None):
        super().__init__(api, erd_code, erd_override, icon_on_override, icon_off_override, device_class_override)
        self._converter = bool_converter

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return self._converter.boolify(self.appliance.get_erd_value(self.erd_code))

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug(f"Turning on {self.unique_id}")
        await self.appliance.async_set_erd_value(self.erd_code, self._converter.true_value())

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        _LOGGER.debug(f"Turning on {self.unique_id}")
        await self.appliance.async_set_erd_value(self.erd_code, self._converter.false_value())
