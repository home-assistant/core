"""Constants for the SilverCrest Infrared integration."""

from enum import StrEnum

DOMAIN = "silvercrest_infrared"
CONF_INFRARED_ENTITY_ID = "infrared_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SilverCrestIrDeviceType(StrEnum):
    """SilverCrest Infrared device types."""

    SML330A1 = "sml330a1"
    SSVF45A1 = "ssvf45a1"
    SSVF45B1 = "ssvf45b1"
    SSVF45C1 = "ssvf45c1"
    SSVS85A1 = "ssvs85a1"
    SSVS85B2 = "ssvs85b2"
    STVD45A1 = "stvd45a1"
    STVL50A1 = "stvl50a1"
    STVL50B1 = "stvl50b1"
    STVL50C1 = "stvl50c1"
    SV60A1 = "sv60a1"
    SV60A2 = "sv60a2"


DEVICE_NAMES = {
    SilverCrestIrDeviceType.SML330A1: "Portable air cooler SML 330 A1",
    SilverCrestIrDeviceType.SSVF45A1: "Pedestal fan SSVF 45 A1",
    SilverCrestIrDeviceType.SSVF45B1: "Pedestal fan SSVF 45 B1",
    SilverCrestIrDeviceType.SSVF45C1: "Pedestal fan SSVF 45 C1",
    SilverCrestIrDeviceType.SSVS85A1: "Misting pedestal fan SSVS 85 A1",
    SilverCrestIrDeviceType.SSVS85B2: "Misting pedestal fan SSVS 85 B2",
    SilverCrestIrDeviceType.STVD45A1: "Tower fan STVD 45 A1",
    SilverCrestIrDeviceType.STVL50B1: "Tower fan STVL 50 B1",
    SilverCrestIrDeviceType.STVL50C1: "Tower fan STVL 50 C1",
    SilverCrestIrDeviceType.SV60A1: "Pedestal fan SV 60 A1",
    SilverCrestIrDeviceType.SV60A2: "Pedestal fan SV 60 A2",
}

MISTING_FANS = {SilverCrestIrDeviceType.SSVS85A1, SilverCrestIrDeviceType.SSVS85B2}
