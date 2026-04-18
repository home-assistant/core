"""Conftest for the SyncThru integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pysyncthru import SyncthruState
import pytest

from homeassistant.components.syncthru.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_URL

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.syncthru.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_syncthru() -> Generator[AsyncMock]:
    """Mock the SyncThru class."""
    with (
        patch(
            "homeassistant.components.syncthru.coordinator.SyncThru",
            autospec=True,
        ) as mock_syncthru,
        patch(
            "homeassistant.components.syncthru.config_flow.SyncThru", new=mock_syncthru
        ),
    ):
        client = mock_syncthru.return_value
        client.model.return_value = "C430W"
        client.is_unknown_state.return_value = False
        client.url = "http://192.168.1.2"
        client.model.return_value = "C430W"
        client.hostname.return_value = "SEC84251907C415"
        client.serial_number.return_value = "08HRB8GJ3F019DD"
        client.device_status.return_value = SyncthruState(3)
        client.device_status_details.return_value = ""
        client.is_online.return_value = True
        client.toner_status.return_value = {
            "black": {"opt": 1, "remaining": 8, "cnt": 1176, "newError": "C1-5110"},
            "cyan": {"opt": 1, "remaining": 98, "cnt": 25, "newError": ""},
            "magenta": {"opt": 1, "remaining": 98, "cnt": 25, "newError": ""},
            "yellow": {"opt": 1, "remaining": 97, "cnt": 27, "newError": ""},
        }
        client.drum_status.return_value = {}
        client.input_tray_status.return_value = {
            "tray_1": {
                "opt": 1,
                "paper_size1": 4,
                "paper_size2": 0,
                "paper_type1": 2,
                "paper_type2": 0,
                "paper_level": 0,
                "capa": 150,
                "newError": "",
            }
        }
        client.output_tray_status.return_value = {
            1: {"name": 1, "capacity": 50, "status": ""}
        }
        client.raw.return_value = load_json_object_fixture("state.json", DOMAIN)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="C430W",
        data={CONF_URL: "http://192.168.1.2/", CONF_NAME: "My Printer"},
    )
