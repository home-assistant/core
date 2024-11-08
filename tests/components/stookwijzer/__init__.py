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

EPSG_URL = f"https://epsg.io/srs/transform/{CONF_INPUT[CONF_LOCATION][CONF_LONGITUDE]},{CONF_INPUT[CONF_LOCATION][CONF_LATITUDE]}.json?key=default&s_srs=4326&t_srs=28992"
STOOKWIJZER_URL = f"https://data.rivm.nl/geo/{"a"}lo/wms?service=WMS&SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&FORMAT=image/png&TRANSPARENT=true&QUERY_LAYERS=stookwijzer_v2&LAYERS=stookwijzer_v2&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8&STYLES=&BUFFER=1&EXCEPTIONS=INIMAGE&info_format=application/json&feature_count=1&I=139&J=222&WIDTH=256&HEIGHT=256&CRS=EPSG:28992&BBOX={CONF_DATA[CONF_LATITUDE]}%2C{CONF_DATA[CONF_LONGITUDE]}%2C{CONF_DATA[CONF_LATITUDE]+10}%2C{CONF_DATA[CONF_LONGITUDE]+10}"


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
    version: int = 2,
    available: bool = True,
    setup: bool = True,
) -> MockConfigEntry:
    """Set up the Stookwijzer integration in Home Assistant."""

    if available:
        mock_available(aioclient_mock)
    else:
        mock_unavailable(aioclient_mock)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="Stookwijzer-test",
        data=CONF_INPUT,
        version=version,
        title=DOMAIN,
    )
    entry.add_to_hass(hass)

    if setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
