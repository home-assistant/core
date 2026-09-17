"""API helpers for the Entur public transport integration."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ENTUR_CLIENT_NAME, ENTUR_STOP_PLACE_URL, GEOCODER_AUTOCOMPLETE_URL


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
