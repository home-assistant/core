"""Type definitions for Nest."""

from dataclasses import dataclass

from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.config_entries import ConfigEntry


@dataclass
class NestData:
    """Data for the Nest integration."""

    subscriber: GoogleNestSubscriber
    device_manager: DeviceManager


type NestConfigEntry = ConfigEntry[NestData]
