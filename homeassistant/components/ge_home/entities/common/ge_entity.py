from datetime import timedelta
from typing import Optional, Dict, Any

from gehomesdk import GeAppliance
from ...devices import ApplianceApi

class GeEntity:
    """Base class for all GE Entities"""
    should_poll = False

    def __init__(self, api: ApplianceApi):
        self._api = api
        self.hass = None

    @property
    def unique_id(self) -> str:
        raise NotImplementedError

    @property
    def api(self) -> ApplianceApi:
        return self._api

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        return self.api.device_info

    @property
    def serial_number(self):
        return self.api.serial_number

    @property
    def available(self) -> bool:
        return self.api.available

    @property
    def appliance(self) -> GeAppliance:
        return self.api.appliance

    @property
    def mac_addr(self) -> str:
        return self.api.mac_addr

    @property
    def serial_or_mac(self) -> str:
        return self.api.serial_or_mac

    @property
    def name(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def icon(self) -> Optional[str]:
        return self._get_icon()

    @property
    def device_class(self) -> Optional[str]:
        return self._get_device_class()    

    def _stringify(self, value: any, **kwargs) -> Optional[str]:
        if isinstance(value, timedelta):
            return str(value)[:-3] if value else ""
        if value is None:
            return None
        return self.appliance.stringify_erd_value(value, **kwargs)

    def _boolify(self, value: any) -> Optional[bool]:
        return self.appliance.boolify_erd_value(value)

    def _get_icon(self) -> Optional[str]:
        return None

    def _get_device_class(self) -> Optional[str]:
        return None
