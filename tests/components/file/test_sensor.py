"""The tests for local file sensor platform."""
from unittest.mock import Mock, patch

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_value(hass: HomeAssistant) -> None:
    """Test the File sensor."""
    config = {
        "sensor": {
            "platform": "file",
            "name": "file1",
            "file_path": get_fixture_path("file_value.txt", "file"),
        }
    }

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.file1")
    assert state.state == "21"


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_value_template(hass: HomeAssistant) -> None:
    """Test the File sensor with JSON entries."""
    config = {
        "sensor": {
            "platform": "file",
            "name": "file2",
            "file_path": get_fixture_path("file_value_template.txt", "file"),
            "value_template": "{{ value_json.temperature }}",
        }
    }

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.file2")
    assert state.state == "26"


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_empty(hass: HomeAssistant) -> None:
    """Test the File sensor with an empty file."""
    config = {
        "sensor": {
            "platform": "file",
            "name": "file3",
            "file_path": get_fixture_path("file_empty.txt", "file"),
        }
    }

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.file3")
    assert state.state == STATE_UNKNOWN


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_path_invalid(hass: HomeAssistant) -> None:
    """Test the File sensor with invalid path."""
    config = {
        "sensor": {
            "platform": "file",
            "name": "file4",
            "file_path": get_fixture_path("file_value.txt", "file"),
        }
    }

    with patch.object(hass.config, "is_allowed_path", return_value=False):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("sensor")) == 0
