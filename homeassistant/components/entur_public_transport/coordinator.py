"""DataUpdateCoordinator for the Entur public transport integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError
from enturclient import EnturPublicTransportData
from enturclient.dto.place import Place

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_CLIENT_NAME,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=45)

type EnturConfigEntry = ConfigEntry[EnturCoordinator]


class EnturCoordinator(DataUpdateCoordinator[dict[str, Place]]):
    """Coordinator for fetching Entur public transport data."""

    config_entry: EnturConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: EnturConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        # Get configuration
        data = {**config_entry.data, **config_entry.options}
        stop_ids = data[CONF_STOP_IDS]
        stops = [s for s in stop_ids if "StopPlace" in s]
        quays = [s for s in stop_ids if "Quay" in s]

        self.client = EnturPublicTransportData(
            API_CLIENT_NAME,
            stops=stops,
            quays=quays,
            line_whitelist=data.get(CONF_WHITELIST_LINES) or [],
            omit_non_boarding=data.get(CONF_OMIT_NON_BOARDING, True),
            number_of_departures=data.get(
                CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
            ),
            web_session=async_get_clientsession(hass),
        )

        self._expand_platforms = data.get(CONF_EXPAND_PLATFORMS, True)
        self._show_on_map = data.get(CONF_SHOW_ON_MAP, False)

    @property
    def show_on_map(self) -> bool:
        """Return whether to show location on map."""
        return self._show_on_map

    async def _async_setup(self) -> None:
        """Perform one-time setup for the coordinator."""
        if self._expand_platforms:
            try:
                await self.client.expand_all_quays()
            except TimeoutError as err:
                raise UpdateFailed(
                    f"Timeout communicating with Entur API: {err}"
                ) from err
            except ClientError as err:
                raise UpdateFailed(
                    f"Error communicating with Entur API: {err}"
                ) from err
            except Exception as err:  # noqa: BLE001
                raise UpdateFailed(
                    f"Unexpected error expanding platforms: {err}"
                ) from err

    async def _async_update_data(self) -> dict[str, Place]:
        """Fetch data from Entur API."""
        try:
            await self.client.update()
        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout communicating with Entur API: {err}"
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                f"Error communicating with Entur API: {err}"
            ) from err

        # Build data dictionary with all stop/quay information
        result: dict[str, Place] = {}
        for place_id in self.client.all_stop_places_quays():
            stop_info = self.client.get_stop_info(place_id)
            if stop_info is not None:
                result[place_id] = stop_info

        return result
