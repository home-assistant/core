"""Support for Ampio Air Quality data."""
from __future__ import annotations

import logging
from typing import Final

from asmog import AmpioSmog
import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    AirQualityEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .const import CONF_STATION_ID, SCAN_INTERVAL

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = BASE_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ampio Smog air quality platform."""

    name = config.get(CONF_NAME)
    station_id = config[CONF_STATION_ID]

    session = async_get_clientsession(hass)
    api = AmpioSmogMapData(AmpioSmog(station_id, hass.loop, session))

    await api.async_update()

    if not api.api.data:
        _LOGGER.error("Station %s is not available", station_id)
        return

    async_add_entities([AmpioSmogQuality(api, station_id, name)], True)


class AmpioSmogQuality(AirQualityEntity):
    """Implementation of an Ampio Smog air quality entity."""

    _attr_attribution = "Data provided by Ampio"

    def __init__(
        self, api: AmpioSmogMapData, station_id: str, name: str | None
    ) -> None:
        """Initialize the air quality entity."""
        self._ampio = api
        self._station_id = station_id
        self._name = name or api.api.name

    @property
    def name(self) -> str:
        """Return the name of the air quality entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique_name."""
        return f"ampio_smog_{self._station_id}"

    @property
    def particulate_matter_2_5(self) -> str | None:
        """Return the particulate matter 2.5 level."""
        return self._ampio.api.pm2_5  # type: ignore[no-any-return]

    @property
    def particulate_matter_10(self) -> str | None:
        """Return the particulate matter 10 level."""
        return self._ampio.api.pm10  # type: ignore[no-any-return]

    async def async_update(self) -> None:
        """Get the latest data from the AmpioMap API."""
        await self._ampio.async_update()


class AmpioSmogMapData:
    """Get the latest data and update the states."""

    def __init__(self, api: AmpioSmog) -> None:
        """Initialize the data object."""
        self.api = api

    @Throttle(SCAN_INTERVAL)
    async def async_update(self) -> None:
        """Get the latest data from AmpioMap."""
        await self.api.get_data()
