"""Data model to represent state of a CCM15 device."""
from dataclasses import dataclass
import logging

from homeassistant.const import (
    UnitOfTemperature,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CCM15SlaveDevice:
    """Data retrieved from a CCM15 slave device."""

    def __init__(self, bytesarr: bytes) -> None:
        """Initialize the slave device."""
        self.unit = UnitOfTemperature.CELSIUS
        buf = bytesarr[0]
        if (buf >> 0) & 1:
            self.unit = UnitOfTemperature.FAHRENHEIT
        self.locked_cool_temperature: int = (buf >> 3) & 0x1F

        buf = bytesarr[1]
        self.locked_heat_temperature: int = (buf >> 0) & 0x1F
        self.locked_wind: int = (buf >> 5) & 7

        buf = bytesarr[2]
        self.locked_ac_mode: int = (buf >> 0) & 3
        self.error_code: int = (buf >> 2) & 0x3F

        buf = bytesarr[3]
        self.ac_mode: int = (buf >> 2) & 7
        self.fan_mode: int = (buf >> 5) & 7

        buf = (buf >> 1) & 1
        self.is_ac_mode_locked: bool = buf != 0

        buf = bytesarr[4]
        self.temperature_setpoint: int = (buf >> 3) & 0x1F
        if self.unit == UnitOfTemperature.FAHRENHEIT:
            self.temperature_setpoint += 62
            self.locked_cool_temperature += 62
            self.locked_heat_temperature += 62
        self.is_swing_on: bool = (buf >> 1) & 1 != 0

        buf = bytesarr[5]
        if ((buf >> 3) & 1) == 0:
            self.locked_cool_temperature = 0
        if ((buf >> 4) & 1) == 0:
            self.locked_heat_temperature = 0
        self.fan_locked: bool = buf >> 5 & 1 != 0
        self.is_remote_locked: bool = ((buf >> 6) & 1) != 0

        buf = bytesarr[6]
        self.temperature: int = buf if buf < 128 else buf - 256


@dataclass
class CCM15DeviceState:
    """Data retrieved from a CCM15 device."""

    devices: list[CCM15SlaveDevice]
