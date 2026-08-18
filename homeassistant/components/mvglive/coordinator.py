"""DataUpdateCoordinator for the MVG integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, override

from mvg import MvgApi, TransportType

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_resilience import call_with_resilience
from .const import DOMAIN, SCAN_INTERVAL
from .messages import fetch_incident_messages

_LOGGER = logging.getLogger(__name__)

type MvgConfigEntry = ConfigEntry[MvgDataUpdateCoordinator]


@dataclass
class MvgData:
    """Raw departures and incident messages for a station."""

    departures: list[dict[str, Any]]
    messages: list[dict[str, Any]]


async def _no_messages() -> list[dict[str, Any]]:
    """Return no messages without calling the API, for when messages are disabled."""
    return []


class MvgDataUpdateCoordinator(DataUpdateCoordinator[MvgData]):
    """Coordinator that polls departures and incident messages for one station."""

    config_entry: MvgConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MvgConfigEntry,
        station_id: str,
        timeoffset: int,
        number: int,
        products: list[str] | None,
        enable_messages: bool,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._station_id = station_id
        self._timeoffset = timeoffset
        self._number = number
        self._enable_messages = enable_messages
        self._transport_types = (
            [product for product in TransportType if product.value[0] in products]
            if products
            else None
        )

    @override
    async def _async_update_data(self) -> MvgData:
        """Fetch departures and incident messages from the MVG API.

        Departures and messages are treated independently: a failure fetching one
        doesn't blank out the other. If a previous successful poll exists, its data
        is kept as a fallback; only a departures failure on the very first refresh
        (no fallback data available) fails the whole update.
        """
        previous = self.data

        departures_result, messages_result = await asyncio.gather(
            call_with_resilience(
                lambda: MvgApi.departures_async(
                    station_id=self._station_id,
                    limit=self._number,
                    offset=self._timeoffset,
                    transport_types=self._transport_types,
                )
            ),
            call_with_resilience(lambda: fetch_incident_messages(self.hass))
            if self._enable_messages
            else _no_messages(),
            return_exceptions=True,
        )

        if isinstance(departures_result, BaseException):
            _LOGGER.warning("Could not update MVG departures: %s", departures_result)
            if previous is None:
                raise UpdateFailed(
                    f"Error fetching departures: {departures_result}"
                ) from departures_result
            departures = previous.departures
        else:
            departures = departures_result

        if isinstance(messages_result, BaseException):
            _LOGGER.warning(
                "Could not update MVG incident messages: %s", messages_result
            )
            messages = previous.messages if previous is not None else []
        else:
            messages = messages_result

        return MvgData(departures=departures, messages=messages)
