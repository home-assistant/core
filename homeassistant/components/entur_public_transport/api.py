"""API helpers for the Entur public transport integration."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ENTUR_CLIENT_NAME,
    ENTUR_STOP_PLACE_URL,
    GEOCODER_AUTOCOMPLETE_URL,
    JOURNEY_PLANNER_URL,
)

STOP_PLACE_LINES_QUERY = """
query StopPlaceLines($stopPlaceId: String!, $numberOfDepartures: Int!) {
  stopPlaces(ids: [$stopPlaceId]) {
    estimatedCalls(numberOfDepartures: $numberOfDepartures) {
      serviceJourney {
        journeyPattern {
          line {
            id
            publicCode
            transportMode
          }
        }
      }
    }
  }
}
"""


class EnturApiError(Exception):
    """Raised when the Entur API cannot be queried or parsed."""


@dataclass(frozen=True, slots=True)
class EnturStopPlace:
    """A stop place returned by the Entur Geocoder."""

    stop_id: str
    name: str
    display_name: str
    locality: str
    transport_modes: tuple[str, ...]
    role: str

    @property
    def selection_label(self) -> str:
        """Return a context-rich label for the Home Assistant selector."""
        details = [self.display_name]
        if (
            self.locality
            and self.locality.casefold() not in self.display_name.casefold()
        ):
            details.append(self.locality)
        if self.transport_modes:
            details.append(", ".join(self.transport_modes))
        return " · ".join(details)

    @property
    def entur_url(self) -> str:
        """Return the Entur departure board URL for this stop place."""
        return ENTUR_STOP_PLACE_URL.format(quote(self.stop_id, safe=""))


@dataclass(frozen=True, slots=True)
class EnturRoute:
    """A route serving an Entur stop place."""

    line_id: str
    public_code: str
    transport_mode: str

    @property
    def selection_label(self) -> str:
        """Return a user-friendly route label."""
        operator = self.line_id.split(":Line:", 1)[0]
        return f"{self.public_code} · {self.transport_mode} · {operator}"


async def async_search_stop_places(
    hass: HomeAssistant, query: str
) -> tuple[EnturStopPlace, ...]:
    """Search Entur stop places by name."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            GEOCODER_AUTOCOMPLETE_URL,
            params={
                "q": query,
                "lang": "no",
                "limit": 10,
                "layers": "stopPlace",
                "multimodal": "parent",
            },
            headers={"ET-Client-Name": ENTUR_CLIENT_NAME},
        ) as response:
            response.raise_for_status()
            payload: Any = await response.json()
    except (ClientError, TimeoutError) as err:
        raise EnturApiError from err

    return _parse_stop_places(payload)


async def async_get_stop_routes(
    hass: HomeAssistant, stop_id: str
) -> tuple[EnturRoute, ...]:
    """Return routes currently serving a stop place."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            JOURNEY_PLANNER_URL,
            json={
                "query": STOP_PLACE_LINES_QUERY,
                "variables": {
                    "stopPlaceId": stop_id,
                    "numberOfDepartures": 50,
                },
            },
            headers={
                "Content-Type": "application/json",
                "ET-Client-Name": ENTUR_CLIENT_NAME,
            },
        ) as response:
            response.raise_for_status()
            payload: Any = await response.json()
    except (ClientError, TimeoutError) as err:
        raise EnturApiError from err

    return _parse_stop_routes(payload)


def _parse_stop_places(payload: Any) -> tuple[EnturStopPlace, ...]:
    """Parse Geocoder v3 stop place results."""
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise EnturApiError

    places = []
    for feature in payload["features"]:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue

        stop_id = properties.get("id")
        if not isinstance(stop_id, str) or not stop_id.startswith("NSR:StopPlace:"):
            continue

        names = properties.get("names")
        names = names if isinstance(names, dict) else {}
        name = names.get("default") or names.get("display") or stop_id
        name = name if isinstance(name, str) else stop_id
        display_name = names.get("display") or name
        display_name = display_name if isinstance(display_name, str) else name

        address = properties.get("address")
        address = address if isinstance(address, dict) else {}
        locality = address.get("locality") or ""
        locality = locality if isinstance(locality, str) else ""

        modes = properties.get("transportModes")
        transport_modes = (
            tuple(
                mode["mode"]
                for mode in modes
                if isinstance(mode, dict) and isinstance(mode.get("mode"), str)
            )
            if isinstance(modes, list)
            else ()
        )

        role = properties.get("stopPlaceRole", "standalone")
        role = role if isinstance(role, str) else "standalone"

        places.append(
            EnturStopPlace(
                stop_id=stop_id,
                name=name,
                display_name=display_name,
                locality=locality,
                transport_modes=transport_modes,
                role=role,
            )
        )

    return tuple(places)


def _parse_stop_routes(payload: Any) -> tuple[EnturRoute, ...]:
    """Parse routes from a Journey Planner response."""
    if not isinstance(payload, dict) or payload.get("errors"):
        raise EnturApiError

    data = payload.get("data")
    stop_places = data.get("stopPlaces") if isinstance(data, dict) else None
    if not isinstance(stop_places, list):
        raise EnturApiError

    routes: dict[str, EnturRoute] = {}
    for stop_place in stop_places:
        if not isinstance(stop_place, dict):
            continue
        calls = stop_place.get("estimatedCalls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            journey = call.get("serviceJourney")
            pattern = (
                journey.get("journeyPattern") if isinstance(journey, dict) else None
            )
            line = pattern.get("line") if isinstance(pattern, dict) else None
            if not isinstance(line, dict):
                continue
            line_id = line.get("id")
            public_code = line.get("publicCode")
            transport_mode = line.get("transportMode")
            if not all(
                isinstance(value, str)
                for value in (line_id, public_code, transport_mode)
            ):
                continue
            routes.setdefault(
                line_id,
                EnturRoute(
                    line_id=line_id,
                    public_code=public_code,
                    transport_mode=transport_mode,
                ),
            )

    return tuple(routes.values())
