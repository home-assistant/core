"""The test for the version sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from pyhaversion import HaVersionSource, exceptions as pyhaversionexceptions
import pytest

from homeassistant.components.version.sensor import HA_VERSION_SOURCES
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import async_fire_time_changed

MOCK_VERSION = "10.0"


@pytest.mark.parametrize(
    "source,target_source,name",
    (
        (
            ("local", HaVersionSource.LOCAL, "current_version"),
            ("docker", HaVersionSource.CONTAINER, "latest_version"),
            ("hassio", HaVersionSource.SUPERVISOR, "latest_version"),
        )
        + tuple(
            (source, HaVersionSource(source), "latest_version")
            for source in HA_VERSION_SOURCES
            if source != HaVersionSource.LOCAL
        )
    ),
)
async def test_version_source(hass, source, target_source, name):
    """Test the Version sensor with different sources."""
    config = {
        "sensor": {"platform": "version", "source": source, "image": "qemux86-64"}
    }

    with patch("homeassistant.components.version.sensor.HaVersion.get_version"), patch(
        "homeassistant.components.version.sensor.HaVersion.version", MOCK_VERSION
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{name}")
    assert state
    assert state.attributes["source"] == target_source

    assert state.state == MOCK_VERSION


async def test_version_fetch_exception(hass, caplog):
    """Test fetch exception thrown during updates."""
    config = {"sensor": {"platform": "version"}}
    with patch(
        "homeassistant.components.version.sensor.HaVersion.get_version",
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
        "homeassistant.components.version.sensor.HaVersion.get_version",
        side_effect=pyhaversionexceptions.HaVersionParseException,
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()
        assert "Could not parse data received for HaVersionSource.LOCAL" in caplog.text


async def test_update(hass):
    """Test updates."""
    config = {"sensor": {"platform": "version"}}

    with patch("homeassistant.components.version.sensor.HaVersion.get_version"), patch(
        "homeassistant.components.version.sensor.HaVersion.version", MOCK_VERSION
    ):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_version")
    assert state
    assert state.state == MOCK_VERSION

    with patch("homeassistant.components.version.sensor.HaVersion.get_version"), patch(
        "homeassistant.components.version.sensor.HaVersion.version", "1234"
    ):

        async_fire_time_changed(hass, dt.utcnow() + timedelta(minutes=5))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.current_version")
    assert state
    assert state.state == "1234"


async def test_image_name_container(hass):
    """Test the Version sensor with image name for container."""
    config = {
        "sensor": {"platform": "version", "source": "docker", "image": "qemux86-64"}
    }

    with patch("homeassistant.components.version.sensor.HaVersion") as haversion:
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    constructor = haversion.call_args[1]
    assert constructor["source"] == "container"
    assert constructor["image"] == "qemux86-64-homeassistant"


async def test_image_name_supervisor(hass):
    """Test the Version sensor with image name for supervisor."""
    config = {
        "sensor": {"platform": "version", "source": "hassio", "image": "qemux86-64"}
    }

    with patch("homeassistant.components.version.sensor.HaVersion") as haversion:
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    constructor = haversion.call_args[1]
    assert constructor["source"] == "supervisor"
    assert constructor["image"] == "qemux86-64"
