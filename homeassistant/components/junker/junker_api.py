"""Asynchronous client for Junker's public collection calendar pages."""

from dataclasses import dataclass
from datetime import date
import json
import re
import unicodedata

from aiohttp import ClientError, ClientResponseError, ClientSession

_BASE_URL = "https://differenziata.junkerapp.it"
_EVENTS_RE = re.compile(r"var\s+events\s*=\s*(\[.*?\])\s*;", re.DOTALL)
_ZONES_RE = re.compile(r"var\s+zone\s*=\s*(\[.*?\])\s*;", re.DOTALL)
_AREA_NAME_KEY = "NOME"  # codespell:ignore nome


class JunkerError(Exception):
    """Base error for Junker calendar requests."""


class JunkerConnectionError(JunkerError):
    """Raised when Junker cannot be reached."""


class AreaRequired(JunkerError):
    """Raised when a municipality requires an area selection."""

    def __init__(self, areas: list[Area]) -> None:
        """Initialize the error with the available areas."""
        self.areas = areas
        super().__init__("An area is required for this municipality")


@dataclass(frozen=True, slots=True)
class Area:
    """An area supplied by Junker."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Collection:
    """A scheduled waste collection."""

    date: date
    waste_type: str


def slugify_municipality(municipality: str) -> str:
    """Convert a municipality name into Junker's URL format."""
    normalized = unicodedata.normalize("NFD", municipality)
    without_accents = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return without_accents.casefold().strip().replace(" ", "-").replace("'", "-")


class JunkerClient:
    """Fetch collection calendars from Junker's public pages."""

    def __init__(
        self, session: ClientSession, municipality: str, area_id: str | None = None
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._municipality = municipality
        self._area_id = area_id

    async def async_get_collections(self) -> list[Collection]:
        """Return the municipality's scheduled waste collections."""
        slug = slugify_municipality(self._municipality)
        path = f"{slug}/calendario"
        if self._area_id is not None:
            path = f"{slug}/{self._area_id}/calendario"
        try:
            async with self._session.get(f"{_BASE_URL}/{path}") as response:
                response.raise_for_status()
                page = await response.text()
        except ClientResponseError as err:
            if err.status < 500:
                raise JunkerError("The Junker calendar was not found") from err
            raise JunkerConnectionError("Junker returned a server error") from err
        except (ClientError, TimeoutError) as err:
            raise JunkerConnectionError(
                "Unable to request the Junker calendar"
            ) from err

        if zones_match := _ZONES_RE.search(page):
            areas = self._parse_areas(zones_match.group(1))
            if areas:
                raise AreaRequired(areas)

        events_match = _EVENTS_RE.search(page)
        if events_match is None:
            raise JunkerError("No collection calendar was found")
        return self._parse_collections(events_match.group(1))

    @staticmethod
    def _parse_areas(raw_areas: str) -> list[Area]:
        """Parse the areas embedded in a calendar page."""
        try:
            areas = json.loads(raw_areas)
            return [Area(id=area["ID"], name=area[_AREA_NAME_KEY]) for area in areas]
        except (KeyError, TypeError, json.JSONDecodeError) as err:
            raise JunkerError("Invalid area data in Junker calendar") from err

    @staticmethod
    def _parse_collections(raw_events: str) -> list[Collection]:
        """Parse the events embedded in a calendar page."""
        try:
            events = json.loads(raw_events)
            collections = [
                Collection(
                    date=date.fromisoformat(event["date"]),
                    waste_type=event["vbin_desc"],
                )
                for event in events
            ]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
            raise JunkerError("Invalid collection data in Junker calendar") from err
        if not collections:
            raise JunkerError("No collections were found")
        return sorted(collections, key=lambda collection: collection.date)
