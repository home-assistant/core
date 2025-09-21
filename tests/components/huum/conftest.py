"""Configuration for Huum tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from huum.const import SaunaStatus
import pytest

from homeassistant.components.huum.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_huum() -> Generator[AsyncMock]:
    """Mock data from the API."""
    huum = AsyncMock()
    with (
        patch(
            "homeassistant.components.huum.config_flow.Huum.status",
            return_value=huum,
        ),
        patch(
            "homeassistant.components.huum.coordinator.Huum.status",
            return_value=huum,
        ),
        patch(
            "homeassistant.components.huum.coordinator.Huum.turn_on",
            return_value=huum,
        ) as turn_on,
        patch(
            "homeassistant.components.huum.coordinator.Huum.toggle_light",
            return_value=huum,
        ) as toggle_light,
    ):
        huum.status = SaunaStatus.ONLINE_NOT_HEATING
        huum.config = 3
        huum.door_closed = True
        huum.temperature = 30
        huum.sauna_name = 123456
        huum.target_temperature = 80
        huum.light = 1
        huum.humidity = 5
        huum.sauna_config.child_lock = "OFF"
        huum.sauna_config.max_heating_time = 3
        huum.sauna_config.min_heating_time = 0
        huum.sauna_config.max_temp = 110
        huum.sauna_config.min_temp = 40
        huum.sauna_config.max_timer = 0
        huum.sauna_config.min_timer = 0
        huum.turn_on = turn_on
        huum.toggle_light = toggle_light

        yield huum


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.huum.async_setup_entry", return_value=True
    ) as setup_entry_mock:
        yield setup_entry_mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "huum@sauna.org",
            CONF_PASSWORD: "ukuuku",
        },
        unique_id="123456",
        entry_id="AABBCC112233",
    )
