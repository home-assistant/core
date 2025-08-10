"""Models for the mystrom integration."""

from dataclasses import dataclass
from typing import Any

from pymystrom.bulb import MyStromBulb
from pymystrom.switch import MyStromSwitch

from homeassistant.config_entries import ConfigEntry

type MyStromConfigEntry = ConfigEntry[MyStromData]


@dataclass
class MyStromData:
    """Data class for mystrom device data."""

    device: MyStromSwitch | MyStromBulb
    info: dict[str, Any]
