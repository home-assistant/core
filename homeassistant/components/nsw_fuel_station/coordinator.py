"""DataUpdateCoordinator for nsw_fuel_ui."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.nsw_fuel_station.const import DOMAIN
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from nsw_fuel import (
    NSWFuelApiClient,
    NSWFuelApiClientAuthError,
    NSWFuelApiClientError,
    Price,
    StationPrice,
)

from .const import (
    DEFAULT_FUEL_TYPE,
    DEFAULT_RADIUS_KM,
    E10_AVAILABLE_STATES,
    E10_CODE,
    E10_TRUNCATE_LIST,
)
from .data import CoordinatorData, StationKey

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NSWFuelCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Manages updates from NSW Fuel Check API."""

    data: CoordinatorData | None

    def __init__(
        self,
        hass: HomeAssistant,
        api: NSWFuelApiClient,
        nicknames: dict[str, dict[str, Any]],
        scan_interval: timedelta,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )

        self.api = api

        # Build a deduplicated set of station keys used for fetching prices.c
        self._station_keys: set[StationKey] = set()
        for nickname_data in nicknames.values():
            for station in nickname_data.get("stations", []):
                self._station_keys.add((station["station_code"], station["au_state"]))

        self._nickname_locations = self._extract_nickname_locations(nicknames)

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch updated fuel prices for all configured stations."""
        try:
            favorites = await self._update_favorite_stations()

            cheapest = await self._update_cheapest_stations()

        except NSWFuelApiClientAuthError:
            _LOGGER.error("Authentication failed")
            raise ConfigEntryAuthFailed from None

        except NSWFuelApiClientError as err:
            msg = f"Error fetching NSW Fuel API: {err}"
            _LOGGER.error("%s", msg)
            raise UpdateFailed(msg) from err

        return {
            "favorites": favorites,
            "cheapest": cheapest,
        }

    async def _update_favorite_stations(self) -> dict[StationKey, dict[str, Price]]:
        """
            Fetch prices for user's favorite stations.

        Returns:
            Dict mapping station keys (station_code, au_state) to dictionaries
            of fuel types and their corresponding prices.
            {
                (station_code, au_state): {
                    "fuel_type": Price,
                    ...
                },
                ...
            }

        """
        favorites: dict[StationKey, dict[str, Price]] = {}

        for station_code, au_state in self._station_keys:
            prices: list[Price] = await self.api.get_fuel_prices_for_station(
                str(station_code),
                au_state,
            )

            favorites[(station_code, au_state)] = {
                p.fuel_type: p for p in prices if p.fuel_type and p.price is not None
            }

        return favorites

    async def _update_cheapest_stations(self) -> dict[str, list[dict]]:
        """
        Fetch cheapest fuel prices per nickname.

        Currently NSW has E10 availability legislation, E10 rare in TAS.

        Returns:
            Dict[str, List[Dict]] with structure:
            {
                nickname: [
                    {
                        "price": float,
                        "station_code": int,
                        "station_name": str,
                        "au_state": str,
                        "fuel_type": str,
                    },
                    ...
                ]
            }

        """
        cheapest: dict[str, list[dict]] = {}

        for nickname, (lat, lon) in self._nickname_locations.items():
            # U91 most reliable/sensible results
            default_nearby = await self.api.get_fuel_prices_within_radius(
                latitude=lat,
                longitude=lon,
                radius=DEFAULT_RADIUS_KM,
                fuel_type=DEFAULT_FUEL_TYPE,
            )

            # Sensors will go unavailable on error
            if not default_nearby:
                _LOGGER.warning("Failed to find prices for %s", nickname)
                continue

            state = default_nearby[0].station.au_state

            def _convert(sp: StationPrice, fuel_type: str) -> dict:
                return {
                    "price": sp.price.price,
                    "station_code": sp.station.code,
                    "station_name": sp.station.name,
                    "au_state": sp.station.au_state,
                    "fuel_type": fuel_type,
                }

            combined: list[dict] = [
                _convert(sp, DEFAULT_FUEL_TYPE) for sp in default_nearby
            ]

            # Get E10 if available and merge with U91
            if state in E10_AVAILABLE_STATES:
                e10_nearby = await self.api.get_fuel_prices_within_radius(
                    latitude=lat,
                    longitude=lon,
                    radius=DEFAULT_RADIUS_KM,
                    fuel_type=E10_CODE,
                )

                combined.extend(
                    _convert(sp, E10_CODE) for sp in e10_nearby[:E10_TRUNCATE_LIST]
                )
            # The API appears to balance price and distance already
            # The sensor will hold the cheapest from both U91 and E10
            # and maybe include stations a little further away.
            combined.sort(key=lambda x: x["price"])
            combined = combined[:2]

            cheapest[nickname] = combined

        return cheapest

    def _extract_nickname_locations(
        self,
        nicknames: dict[str, dict[str, Any]],
    ) -> dict[str, tuple[float, float]]:
        """
        Extract and validate latitude/longitude per nickname.

        API call requires lat/lon, retrieve for each nickname.
        """
        locations: dict[str, tuple[float, float]] = {}

        for nickname, nickname_data in nicknames.items():
            location = nickname_data.get("location")

            if not isinstance(location, dict):
                msg = f"Nickname '{nickname}' must include a location block"
                raise TypeError(msg)

            lat = location.get("latitude")
            lon = location.get("longitude")

            if lat is None or lon is None:
                msg = f"Nickname '{nickname}' must include latitude and longitude"
                raise ValueError(msg)

            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                msg = f"Latitude/longitude for nickname '{nickname}' must be numeric"
                raise TypeError(msg)

            locations[nickname] = (float(lat), float(lon))

        if not locations:
            msg = "At least one nickname with location is required"
            raise ValueError(msg)

        return locations

    @property
    def nicknames(self) -> list[str]:
        """Return list of configured nicknames."""
        return list(self._nickname_locations.keys())
