from gehomesdk import ErdCode, ErdOperatingMode

from ..common import GeErdSwitch

# TODO: This is actually controlled through the 0x3007 ERD value (SOUND).
#       The conversions are a pain in the butt, so this will be left for later.
class GeDishwasherControlLockedSwitch(GeErdSwitch):
    @property
    def is_on(self) -> bool:
        mode: ErdOperatingMode = self.appliance.get_erd_value(ErdCode.OPERATING_MODE)
        return mode == ErdOperatingMode.CONTROL_LOCKED
    
