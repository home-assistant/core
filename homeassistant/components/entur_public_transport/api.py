"""Thin Home Assistant adapter and presentation helpers for Entur discovery."""

from enturclient import (
    EnturDiscoveryClient,
    EnturPublicTransportData,
    EnturQuay,
    EnturRoute,
    EnturStopPlace,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ENTUR_CLIENT_NAME


def _client(hass: HomeAssistant) -> EnturDiscoveryClient:
    """Build an Entur client using Home Assistant's shared HTTP session."""
    return EnturDiscoveryClient(ENTUR_CLIENT_NAME, async_get_clientsession(hass))


async def async_search_stop_places(
    hass: HomeAssistant, query: str
) -> tuple[EnturStopPlace, ...]:
    """Search Entur stop places by name."""
    return await _client(hass).async_search_stop_places(query)


async def async_get_stop_place(hass: HomeAssistant, stop_id: str) -> EnturStopPlace:
    """Return one stop place by its canonical ID."""
    return await _client(hass).async_get_stop_place(stop_id)


async def async_get_stop_routes(
    hass: HomeAssistant, stop_id: str
) -> tuple[EnturRoute, ...]:
    """Return routes currently serving a stop place."""
    return await _client(hass).async_get_stop_routes(stop_id)


async def async_get_stop_quays(
    hass: HomeAssistant, stop_id: str
) -> tuple[EnturQuay, ...]:
    """Return active quays/platforms belonging to a stop place."""
    return await _client(hass).async_get_stop_quays(stop_id)


async def async_get_expanded_stop_quays(
    hass: HomeAssistant, stop_id: str, line_whitelist: list[str]
) -> tuple[str, ...]:
    """Return the quays that sensor setup will create for a stop place."""
    data = EnturPublicTransportData(
        ENTUR_CLIENT_NAME,
        stops=[stop_id],
        line_whitelist=line_whitelist,
        web_session=async_get_clientsession(hass),
    )
    await data.expand_all_quays()
    return tuple(data.quays)


def line_id_label(line_id: str) -> str:
    """Return a useful fallback label for a manually entered line ID."""
    authority, separator, line_code = line_id.partition(":Line:")
    if separator:
        return f"{line_code} {authority} ({line_code}-{authority})"
    return line_id


def format_stop_place_title(
    name: str,
    type_icons: str,
    line_ids: list[str],
    route_labels: dict[str, str],
) -> str:
    """Return the title shown for a configured stop place subentry."""
    route_summary = (
        ", ".join(
            route_labels.get(line_id, line_id_label(line_id)) for line_id in line_ids
        )
        if line_ids
        else "all routes"
    )
    return f"{type_icons} {name} · {route_summary}"
