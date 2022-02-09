from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity

from gehomesdk import ErdCode, ErdCodeType, ErdCodeClass
from ...devices import ApplianceApi
from .ge_erd_entity import GeErdEntity


class GeErdBinarySensor(GeErdEntity, BinarySensorEntity):
    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType, erd_override: str = None, icon_on_override: str = None, icon_off_override: str = None, device_class_override: str = None):
        super().__init__(api, erd_code, erd_override=erd_override, icon_override=icon_on_override, device_class_override=device_class_override)
        self._icon_on_override = icon_on_override
        self._icon_off_override = icon_off_override

    """GE Entity for binary sensors"""
    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._boolify(self.appliance.get_erd_value(self.erd_code))

    def _get_icon(self):
        if self._icon_on_override and self.is_on:
            return self._icon_on_override
        if self._icon_off_override and not self.is_on:
            return self._icon_off_override

        if self._erd_code_class == ErdCodeClass.DOOR or self.device_class == "door":
            return "mdi:door-open" if self.is_on else "mdi:door-closed"

        return super()._get_icon()

    def _get_device_class(self) -> Optional[str]:
        if self._device_class_override:
            return self._device_class_override
        if self._erd_code_class == ErdCodeClass.DOOR:
            return "door"
        return None
