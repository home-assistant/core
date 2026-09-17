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
    GEOCODER_PLACE_URL,
    JOURNEY_PLANNER_URL,
    STOP_PLACE_TYPE_ICONS,
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
            name
            transportMode
          }
        }
      }
    }
  }
}
"""

STOP_PLACE_QUAYS_QUERY = """
query StopPlaceQuays($stopPlaceId: String!) {
  stopPlaces(ids: [$stopPlaceId]) {
    quays(filterByInUse: true) {
      id
      name
      publicCode
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
    stop_place_types: tuple[str, ...] = ()

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

    @property
    def type_icons(self) -> str:
        """Return icons for all stop place types supplied by Entur."""
        icons = dict.fromkeys(
            STOP_PLACE_TYPE_ICONS.get(stop_place_type, "🚉")
            for stop_place_type in self.stop_place_types
        )
        return " ".join(icons) or "🚏"


@dataclass(frozen=True, slots=True)
class EnturRoute:
    """A route serving an Entur stop place."""

    line_id: str
    public_code: str
    transport_mode: str
    name: str | None = None

    @property
    def operator_code(self) -> str:
        """Return the operator/authority code from the Entur line ID."""
        authority, separator, _ = self.line_id.partition(":Line:")
        return authority if separator else ""

    @property
    def technical_id(self) -> str:
        """Return the line ID in a compact, user-readable form."""
        authority, separator, line_code = self.line_id.partition(":Line:")
        if not separator:
            return self.line_id
        return f"{line_code}-{authority}"

    @property
    def selection_label(self) -> str:
        """Return a user-friendly route label."""
        public_code = self.public_code
        if "_" in public_code and self.name:
            name_code = self.name.split(maxsplit=1)[0]
            if name_code:
                public_code = name_code
        operator = self.operator_code
        route_label = (
            " ".join(part for part in (public_code, operator) if part) or self.line_id
        )
        if self.technical_id != self.line_id:
            route_label += f" ({self.technical_id})"
        return route_label


@dataclass(frozen=True, slots=True)
class EnturQuay:
    """A quay/platform belonging to an Entur stop place."""

    quay_id: str
    name: str
    public_code: str | None

    @property
    def selection_label(self) -> str:
        """Return a concise label for the platform selector."""
        if self.public_code:
            return f"{self.public_code} · {self.name}"
        return self.name


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
    except (ClientError, TimeoutError, ValueError) as err:
        raise EnturApiError from err

    return _parse_stop_places(payload)


async def async_get_stop_place(hass: HomeAssistant, stop_id: str) -> EnturStopPlace:
    """Return one stop place from the Geocoder by its canonical ID."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            GEOCODER_PLACE_URL,
            params={"ids": stop_id, "lang": "no"},
            headers={"ET-Client-Name": ENTUR_CLIENT_NAME},
        ) as response:
            response.raise_for_status()
            payload: Any = await response.json()
    except (ClientError, TimeoutError, ValueError) as err:
        raise EnturApiError from err

    places = _parse_stop_places(payload)
    try:
        return next(place for place in places if place.stop_id == stop_id)
    except StopIteration as err:
        raise EnturApiError from err


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
    except (ClientError, TimeoutError, ValueError) as err:
        raise EnturApiError from err

    return _parse_stop_routes(payload)


async def async_get_stop_quays(
    hass: HomeAssistant, stop_id: str
) -> tuple[EnturQuay, ...]:
    """Return active quays/platforms belonging to a stop place."""
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            JOURNEY_PLANNER_URL,
            json={
                "query": STOP_PLACE_QUAYS_QUERY,
                "variables": {"stopPlaceId": stop_id},
            },
            headers={
                "Content-Type": "application/json",
                "ET-Client-Name": ENTUR_CLIENT_NAME,
            },
        ) as response:
            response.raise_for_status()
            payload: Any = await response.json()
    except (ClientError, TimeoutError, ValueError) as err:
        raise EnturApiError from err

    return _parse_stop_quays(payload)


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

        types = properties.get("stopPlaceTypes")
        stop_place_types = (
            tuple(value for value in types if isinstance(value, str))
            if isinstance(types, list)
            else ()
        )

        places.append(
            EnturStopPlace(
                stop_id=stop_id,
                name=name,
                display_name=display_name,
                locality=locality,
                transport_modes=transport_modes,
                role=role,
                stop_place_types=stop_place_types,
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
            name = line.get("name")
            transport_mode = line.get("transportMode")
            if (
                not isinstance(line_id, str)
                or not isinstance(public_code, str)
                or not isinstance(transport_mode, str)
            ):
                continue
            if not isinstance(name, str):
                name = None
            routes.setdefault(
                line_id,
                EnturRoute(
                    line_id=line_id,
                    public_code=public_code,
                    name=name,
                    transport_mode=transport_mode,
                ),
            )

    return tuple(routes.values())


def _parse_stop_quays(payload: Any) -> tuple[EnturQuay, ...]:
    """Parse active quays from a Journey Planner response."""
    if not isinstance(payload, dict) or payload.get("errors"):
        raise EnturApiError

    data = payload.get("data")
    stop_places = data.get("stopPlaces") if isinstance(data, dict) else None
    if not isinstance(stop_places, list):
        raise EnturApiError

    quays: dict[str, EnturQuay] = {}
    for stop_place in stop_places:
        if not isinstance(stop_place, dict):
            continue
        values = stop_place.get("quays")
        if not isinstance(values, list):
            continue
        for quay in values:
            if not isinstance(quay, dict):
                continue
            quay_id = quay.get("id")
            name = quay.get("name")
            public_code = quay.get("publicCode")
            if not isinstance(quay_id, str) or not isinstance(name, str):
                continue
            if not isinstance(public_code, str):
                public_code = None
            quays.setdefault(
                quay_id,
                EnturQuay(
                    quay_id=quay_id,
                    name=name,
                    public_code=public_code,
                ),
            )

    return tuple(quays.values())
