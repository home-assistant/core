"""Coordinator module for the AirTouch 3 integration."""

from dataclasses import dataclass
import logging
from typing import override

from pyairtouch3 import (
    DEFAULT_PORT,
    Aircon,
    AirTouchClient,
    AirTouchError,
    AirtouchZone,
)

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type AirTouch3ConfigEntry = ConfigEntry[Airtouch3DataUpdateCoordinator]


@dataclass(slots=True)
class AirTouch3Data:
    """Parsed AirTouch 3 coordinator data."""

    aircon: Aircon
    zones: dict[int, AirtouchZone]

    @classmethod
    def from_aircon(cls, aircon: Aircon) -> AirTouch3Data:
        """Create coordinator data with zones keyed by AirTouch zone id."""
        return cls(
            aircon=aircon,
            zones={zone.id: zone for zone in aircon.zones},
        )


async def async_fetch_airtouch_data(host: str, port: int = DEFAULT_PORT) -> Aircon:
    """Fetch and parse data from an AirTouch 3 controller."""
    try:
        aircon = await AirTouchClient(host, port, logger=_LOGGER).fetch_aircon()
    except AirTouchError as err:
        _LOGGER.debug("AirTouch 3 communication with %s:%s failed: %s", host, port, err)
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    if aircon.ac_id is None:
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="update_failed",
            translation_placeholders={"error": "response did not include an AC id"},
        )
    return aircon


class Airtouch3DataUpdateCoordinator(DataUpdateCoordinator[AirTouch3Data]):
    """Class to manage fetching Airtouch 3 data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirTouch3ConfigEntry,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize the Airtouch data updater."""
        assert entry.unique_id is not None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.system_id = entry.unique_id
        self.host = host
        self.port = port
        self.client: AirTouchClient = AirTouchClient(host, port, logger=_LOGGER)

    @override
    async def _async_update_data(self) -> AirTouch3Data:
        """Fetch data from AirTouch."""
        return AirTouch3Data.from_aircon(
            await async_fetch_airtouch_data(self.host, self.port)
        )
