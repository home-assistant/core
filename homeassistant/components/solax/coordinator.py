"""Constants for the solax integration."""

from solax import InverterResponse

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class SolaxDataUpdateCoordinator(DataUpdateCoordinator[InverterResponse]):
    """DataUpdateCoordinator for solax."""
