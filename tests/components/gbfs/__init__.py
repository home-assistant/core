"""Tests for the GBFS integration."""

from pytest_homeassistant.common import get_fixture_path, load_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gbfs.const import DOMAIN

BASE_URL = "https://gbfs.example.com"
V3_URL = f"{BASE_URL}/v3/gbfs.json"
V2_URL = f"{BASE_URL}/v2/gbfs.json"
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
