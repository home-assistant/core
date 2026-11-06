"""Tests for the GBFS integration."""

from collections.abc import Callable
from typing import Any

from pytest_homeassistant.common import (
    async_load_json_object_fixture,
    get_fixture_path,
    load_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gbfs.const import DOMAIN
from homeassistant.core import HomeAssistant

BASE_URL = "https://gbfs.example.com"
V3_URL = f"{BASE_URL}/v3/gbfs.json"
V2_URL = f"{BASE_URL}/v2/gbfs.json"
MIXED_URL = f"{BASE_URL}/v3_mixed/gbfs.json"
DOCKLESS_URL = f"{BASE_URL}/v3_dockless/gbfs.json"
MIRROR_URL = "https://mirror.example.com/v3/gbfs.json"
STATION_SUBENTRY_ID = "station_s1"

DOCUMENTS = (
    "gbfs",
    "system_information",
    "station_information",
    "station_status",
    "vehicle_types",
)


def mock_feed(aioclient_mock: AiohttpClientMocker, version: str) -> None:
    """Serve every document of a fixture system."""
    for name in DOCUMENTS:
        if get_fixture_path(f"{version}/{name}.json", DOMAIN).exists():
            aioclient_mock.get(
                f"{BASE_URL}/{version}/{name}.json",
                text=load_fixture(f"{version}/{name}.json", DOMAIN),
            )


async def serve_edited_v3_feed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    edits: dict[str, Callable[[dict[str, Any]], None]],
) -> None:
    """Serve the v3 fixture system with some documents edited in place."""
    aioclient_mock.clear_requests()
    # Registered first, so they win over the fixture mocks of the same URLs.
    for name, edit in edits.items():
        document = await async_load_json_object_fixture(hass, f"v3/{name}.json", DOMAIN)
        edit(document)
        aioclient_mock.get(f"{BASE_URL}/v3/{name}.json", json=document)
    mock_feed(aioclient_mock, "v3")
