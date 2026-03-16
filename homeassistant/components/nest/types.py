"""Type definitions for Nest."""

from collections.abc import Callable
from dataclasses import dataclass

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.config_entries import ConfigEntry

type DevicesAddedListener = Callable[[list[Device]], None]


@dataclass
class NestData:
    """Data for the Nest integration."""

    subscriber: GoogleNestSubscriber
    device_manager: DeviceManager
    register_devices_listener: Callable[[DevicesAddedListener], None]


type NestConfigEntry = ConfigEntry[NestData]
