"""Tests for the Junker calendar client."""

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.junker.junker_api import (
    _EVENTS_RE,
    AreaRequired,
    JunkerClient,
    JunkerError,
    slugify_municipality,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

AREA_NAME_KEY = "NOME"  # codespell:ignore nome


def test_slugify_municipality() -> None:
    """Test municipality names are converted to Junker URL slugs."""
    assert slugify_municipality("Lodè d'Italia") == "lode-d-italia"


def test_extract_events_from_calendar_page() -> None:
    """Test that events are extracted from Junker's calendar JavaScript."""
    match = _EVENTS_RE.search('var events = [{"date":"2026-11-12"}];')
    assert match is not None
    assert match.group(1) == '[{"date":"2026-11-12"}]'


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        (
            '[{"date":"2026-11-12","vbin_desc":"Paper"}]',
            [("2026-11-12", "Paper")],
        ),
    ],
)
def test_parse_collections(events: str, expected: list[tuple[str, str]]) -> None:
    """Test embedded event data is parsed into collections."""
    collections = JunkerClient._parse_collections(events)
    assert [(str(item.date), item.waste_type) for item in collections] == expected


def test_parse_invalid_collections() -> None:
    """Test invalid event data raises a Junker error."""
    with pytest.raises(JunkerError):
        JunkerClient._parse_collections("[]")


URL = "https://differenziata.junkerapp.it/test-municipality/calendario"
AREA_URL = "https://differenziata.junkerapp.it/test-municipality/1/calendario"
EVENTS = 'var events = [{"date":"2026-11-12","vbin_desc":"Paper"}];'


async def test_get_collections(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetching the collections of a municipality."""
    aioclient_mock.get(URL, text=EVENTS)
    client = JunkerClient(async_get_clientsession(hass), "Test municipality")
    collections = await client.async_get_collections()
    assert [(str(c.date), c.waste_type) for c in collections] == [
        ("2026-11-12", "Paper")
    ]


async def test_get_collections_with_area(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetching the collections of an area."""
    aioclient_mock.get(AREA_URL, text=EVENTS)
    client = JunkerClient(async_get_clientsession(hass), "Test municipality", "1")
    assert len(await client.async_get_collections()) == 1


async def test_area_required(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a municipality with areas requires a selection."""
    aioclient_mock.get(
        URL, text=f'var zone = [{{"ID":1,"{AREA_NAME_KEY}":"Central"}}];'
    )
    client = JunkerClient(async_get_clientsession(hass), "Test municipality")
    with pytest.raises(AreaRequired) as err:
        await client.async_get_collections()
    assert [(a.id, a.name) for a in err.value.areas] == [(1, "Central")]


async def test_empty_areas_use_events(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an empty area list falls back to the events."""
    aioclient_mock.get(URL, text=f"var zone = [];\n{EVENTS}")
    client = JunkerClient(async_get_clientsession(hass), "Test municipality")
    assert len(await client.async_get_collections()) == 1


async def test_invalid_areas(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid area data raises a Junker error."""
    aioclient_mock.get(URL, text='var zone = [{"ID":1}];')
    client = JunkerClient(async_get_clientsession(hass), "Test municipality")
    with pytest.raises(JunkerError):
        await client.async_get_collections()


@pytest.mark.parametrize(
    ("status", "text"),
    [(404, ""), (200, "no calendar here")],
)
async def test_request_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    text: str,
) -> None:
    """Test HTTP errors and pages without events raise a Junker error."""
    aioclient_mock.get(URL, status=status, text=text)
    client = JunkerClient(async_get_clientsession(hass), "Test municipality")
    with pytest.raises(JunkerError):
        await client.async_get_collections()


def test_parse_malformed_collections() -> None:
    """Test malformed event data raises a Junker error."""
    with pytest.raises(JunkerError):
        JunkerClient._parse_collections('[{"date":"x","vbin_desc":"Paper"}]')
