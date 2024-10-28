"""Fixtures for Palazzetti integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.palazzetti.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        unique_id="11:22:33:44:55:66",
    )


@pytest.fixture
def mock_palazzetti_client() -> Generator[AsyncMock]:
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient",
            autospec=True,
        ) as client,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient",
            new=client,
        ),
    ):
        mock_client = client.return_value
        mock_client.mac = "11:22:33:44:55:66"
        mock_client.name = "Stove"
        mock_client.sw_version = "0.0.0"
        mock_client.hw_version = "1.1.1"
        mock_client.fan_speed_min = 1
        mock_client.fan_speed_max = 5
        mock_client.has_fan_silent = True
        mock_client.has_fan_high = True
        mock_client.has_fan_auto = True
        mock_client.has_on_off_switch = True
        mock_client.connected = True
        mock_client.is_heating = True
        mock_client.room_temperature = 18
        mock_client.target_temperature = 21
        mock_client.target_temperature_min = 5
        mock_client.target_temperature_max = 50
        mock_client.fan_speed = 3
        mock_client.connect.return_value = True
        mock_client.update_state.return_value = True
        mock_client.set_on.return_value = True
        mock_client.set_target_temperature.return_value = True
        mock_client.set_fan_speed.return_value = True
        mock_client.set_fan_silent.return_value = True
        mock_client.set_fan_high.return_value = True
        mock_client.set_fan_auto.return_value = True
        yield mock_client
