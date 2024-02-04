"""Helpers for Invoxia (unofficial) integration."""

from dataclasses import dataclass

from gps_tracker import AsyncClient, Config

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession


@dataclass
class GpsTrackerData:
    """Dynamic data associated to a GPS Tracker."""

    latitude: float
    longitude: float
    accuracy: int
    battery: int


def get_invoxia_client(hass: HomeAssistant, config: Config) -> AsyncClient:
    """Create an AsyncClient instance."""
    auth = AsyncClient.get_auth(config)
    session = async_create_clientsession(hass, auth=auth)
    return AsyncClient(config=config, session=session)
