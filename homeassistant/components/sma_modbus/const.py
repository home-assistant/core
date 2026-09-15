"""Constants for the SMA Modbus integration."""

from datetime import timedelta
from enum import StrEnum
from typing import Final

from sma_modbus import DeviceType

DOMAIN: Final = "sma_modbus"

CONF_DEVICE_TYPE: Final = "device_type"
CONF_UNIT_ID: Final = "unit_id"
CONF_WEB_PORT: Final = "web_port"

DEFAULT_PORT: Final = 502


class UnitOfElectricResistance(StrEnum):
    """Electric resistance units."""

    MICROOHM = "μΩ"
    MILLIOHM = "mΩ"
    OHM = "Ω"
    KILOOHM = "kΩ"
    MEGAOHM = "MΩ"


SCAN_INTERVAL: Final = timedelta(seconds=30)

DEVICE_NAMES: dict[DeviceType, str] = {
    DeviceType.SUNNY_HOME_MANAGER: "Sunny Home Manager 2.0",
    DeviceType.SUNNY_BOY_SMART_ENERGY: "Sunny Boy Smart Energy 3.6-6.0",
    DeviceType.SUNNY_BOY: "Sunny Boy 3.0-6.0",
    DeviceType.SUNNY_TRIPOWER: "Sunny Tripower 3.0-6.0",
}
