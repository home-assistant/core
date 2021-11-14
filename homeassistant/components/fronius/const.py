"""Constants for the Fronius integration."""
from typing import Final, NamedTuple

DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_UPDATE_INTERVAL_LOGGER = 60 * 60
DEFAULT_UPDATE_INTERVAL_POWER_FLOW = 10
DOMAIN: Final = "fronius"

SolarNetId = str
SOLAR_NET_ID_POWER_FLOW: SolarNetId = "power_flow"
SOLAR_NET_ID_SYSTEM: SolarNetId = "system"


class FroniusDeviceInfo(NamedTuple):
    """Information about a Fronius inverter device."""

    solar_net_id: SolarNetId
    unique_id: str
