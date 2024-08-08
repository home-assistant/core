"""The tests for local file sensor platform."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.components.file import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_fixture_path


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_value_yaml_setup(
    hass: HomeAssistant, mock_is_allowed_path: MagicMock
) -> None:
    """Test the File sensor from YAML setup."""
    config = {
        "sensor": {
            "platform": "file",
            "scan_interval": 30,
            "name": "file1",
            "file_path": get_fixture_path("file_value.txt", "file"),
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.file1")
    assert state.state == "21"


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_value_entry_setup(
    hass: HomeAssistant, mock_is_allowed_path: MagicMock
) -> None:
    """Test the File sensor from an entry setup."""
    data = {
        "platform": "sensor",
        "name": "file1",
        "file_path": get_fixture_path("file_value.txt", "file"),
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=2,
        options={},
        title=f"test [{data['file_path']}]",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("sensor.file1")
    assert state.state == "21"


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_value_template(
    hass: HomeAssistant, mock_is_allowed_path: MagicMock
) -> None:
    """Test the File sensor with JSON entries."""
    data = {
        "platform": "sensor",
        "name": "file2",
        "file_path": get_fixture_path("file_value_template.txt", "file"),
    }
    options = {
        "value_template": "{{ value_json.temperature }}",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=2,
        options=options,
        title=f"test [{data['file_path']}]",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("sensor.file2")
    assert state.state == "26"


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
async def test_file_empty(hass: HomeAssistant, mock_is_allowed_path: MagicMock) -> None:
    """Test the File sensor with an empty file."""
    data = {
        "platform": "sensor",
        "name": "file3",
        "file_path": get_fixture_path("file_empty.txt", "file"),
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=2,
        options={},
        title=f"test [{data['file_path']}]",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("sensor.file3")
    assert state.state == STATE_UNKNOWN


@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
@pytest.mark.parametrize("is_allowed", [False])
async def test_file_path_invalid(
    hass: HomeAssistant, mock_is_allowed_path: MagicMock
) -> None:
    """Test the File sensor with invalid path."""
    data = {
        "platform": "sensor",
        "name": "file4",
        "file_path": get_fixture_path("file_value.txt", "file"),
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        version=2,
        options={},
        title=f"test [{data['file_path']}]",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    assert len(hass.states.async_entity_ids("sensor")) == 0
