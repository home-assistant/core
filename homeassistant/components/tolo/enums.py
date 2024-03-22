"""Enums for the TOLO integration."""

from enum import Enum

from tololib import AromaTherapySlot as ToloAromaTherapySlot, LampMode as ToloLampMode


class AromaTherapySlot(Enum):
    """Mapping to TOLO Aroma Therapy Slot."""

    A = ToloAromaTherapySlot.A
    B = ToloAromaTherapySlot.B


class LampMode(Enum):
    """Mapping to TOLO Lamp Mode."""

    MANUAL = ToloLampMode.MANUAL
    AUTOMATIC = ToloLampMode.AUTOMATIC
