"""Fixtures for the Sunsynk tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from sunsynk.battery import Battery
from sunsynk.grid import Grid
from sunsynk.input import Input
from sunsynk.inverter import Inverter
from sunsynk.load import Load

from homeassistant.components.sunsynk.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

USERNAME = "test@example.com"
PASSWORD = "test-password"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunsynk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sunsynk_client() -> Generator[AsyncMock]:
    """Mock the Sunsynk API client."""
    with (
        patch(
            "homeassistant.components.sunsynk.SunsynkClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.sunsynk.config_flow.SunsynkClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_inverters.return_value = [
            Inverter(inverter)
            for inverter in load_json_array_fixture("inverters.json", DOMAIN)
        ]
        client.get_inverter_realtime_battery.return_value = Battery(
            load_json_object_fixture("battery.json", DOMAIN)
        )
        client.get_inverter_realtime_grid.return_value = Grid(
            load_json_object_fixture("grid.json", DOMAIN)
        )
        client.get_inverter_realtime_input.return_value = Input(
            load_json_object_fixture("input.json", DOMAIN)
        )
        client.get_inverter_realtime_load.return_value = Load(
            load_json_object_fixture("load.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=USERNAME,
    )
