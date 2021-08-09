"""The test for the version sensor platform."""
from unittest.mock import patch

from pyhaversion import HaVersionSource, exceptions as pyhaversionexceptions
import pytest

from homeassistant.components.version.sensor import ALL_SOURCES
from homeassistant.setup import async_setup_component

MOCK_VERSION = "10.0"


@pytest.mark.parametrize(
    "source",
    ALL_SOURCES,
)
async def test_version_source(hass, source):
    """Test the Version sensor with different sources."""
    config = {
        "sensor": {"platform": "version", "source": source, "image": "qemux86-64"}
    }

    with patch("pyhaversion.version.HaVersion.version", MOCK_VERSION):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    name = "current_version" if source == HaVersionSource.LOCAL else "latest_version"
    state = hass.states.get(f"sensor.{name}")

    assert state.state == MOCK_VERSION


async def test_version_fetch_exception(hass, caplog):
    """Test fetch exception thrown during updates."""
    config = {"sensor": {"platform": "version"}}
    with patch(
        "pyhaversion.version.HaVersion.get_version",
        side_effect=pyhaversionexceptions.HaVersionFetchException(
            "Fetch exception from pyhaversion"
        ),
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        assert "Fetch exception from pyhaversion" in caplog.text


async def test_version_parse_exception(hass, caplog):
    """Test parse exception thrown during updates."""
    config = {"sensor": {"platform": "version"}}
    with patch(
        "pyhaversion.version.HaVersion.get_version",
        side_effect=pyhaversionexceptions.HaVersionParseException,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        assert "Could not parse data received for HaVersionSource.LOCAL" in caplog.text
