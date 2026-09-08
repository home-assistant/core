"""Build a De Dietrich device for a configured system, shared by probe and setup."""

from diematic_modbus import Diematic, DiematicISystem, DiematicVariant
from modbus_connection import ModbusUnit

from .const import SYSTEM_DIEMATIC_3, SYSTEM_DIEMATIC_4

_VARIANTS = {
    SYSTEM_DIEMATIC_3: DiematicVariant.DIEMATIC_3,
    SYSTEM_DIEMATIC_4: DiematicVariant.DIEMATIC_4,
}


def build_device(unit: ModbusUnit, system: str) -> Diematic | DiematicISystem:
    """Build the regulator matching the configured system."""
    # Variant only affects base-layout mode writes, a no-op for iSystem and reads.
    variant = _VARIANTS.get(system)
    if variant is not None:
        return Diematic(unit, variant=variant)
    return DiematicISystem(unit)
