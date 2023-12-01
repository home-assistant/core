"""Tests for the Stookwijzer integration."""
from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

CONF_DATA = {CONF_LATITUDE: 200000.1234567890, CONF_LONGITUDE: 450000.1234567890}
CONF_INPUT = {CONF_LOCATION: {CONF_LATITUDE: 1.0, CONF_LONGITUDE: 1.1}}

A = "a"
EPSG_URL = f"https://epsg.io/srs/transform/{CONF_INPUT[CONF_LOCATION][CONF_LONGITUDE]},{CONF_INPUT[CONF_LOCATION][CONF_LATITUDE]}.json?key=default&s_srs=4326&t_srs=28992"
STOOKWIJZER_URL = f"https://data.rivm.nl/geo/{A}lo/wms?service=WMS&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&FORMAT=application%2Fjson&QUERY_LAYERS=stookwijzer&LAYERS=stookwijzer&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8&STYLES=&BUFFER=1&info_format=application%2Fjson&feature_count=1&I=1&J=1&WIDTH=1&HEIGHT=1&CRS=EPSG%3A28992&BBOX={CONF_DATA[CONF_LATITUDE]}%2C{CONF_DATA[CONF_LONGITUDE]}%2C{CONF_DATA[CONF_LATITUDE]+10}%2C{CONF_DATA[CONF_LONGITUDE]+10}"


def mock_available(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Stookwijzer connections for Home Assistant."""
    aioclient_mock.get(
        EPSG_URL,
        text=load_fixture("epsg_transform.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        STOOKWIJZER_URL,
        text=load_fixture("stookwijzer.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


def mock_unavailable(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Stookwijzer unavailable for Home Assistant."""
    aioclient_mock.get(
        EPSG_URL,
        text=load_fixture("epsg_transform.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(STOOKWIJZER_URL, exc=TimeoutError)


def mock_transform_failure(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Stookwijzer unavailable for Home Assistant."""
    aioclient_mock.get(EPSG_URL, exc=TimeoutError)


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    available: bool = True,
) -> MockConfigEntry:
    """Set up the Stookwijzer integration in Home Assistant."""

    if available:
        mock_available(aioclient_mock)
    else:
        mock_unavailable(aioclient_mock)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=1234,
        data=CONF_INPUT,
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
