"""Fixtures for Palazzetti integration tests."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={
            CONF_NAME: "Stove",
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "11:22:33:44:55:66",
        },
        unique_id="unique_id",
    )


@pytest.fixture
def mock_palazzetti():
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient",
            AsyncMock,
        ) as client,
    ):
        client.connect = AsyncMock(return_value=True)
        client.update_state = AsyncMock(return_value=True)
        client.mac = "11:22:33:44:55:66"
        client.name = "Stove"
        client.sw_version = "0.0.0"
        client.hw_version = "1.1.1"
        client.fan_speed_min = 1
        client.fan_speed_max = 5
        client.has_fan_silent = False
        client.has_fan_high = True
        client.has_fan_auto = True
        client.has_on_off_switch = True
        client.connected = True
        client.is_heating = True
        client.room_temperature = 18
        client.target_temperature = 21
        client.target_temperature_min = 5
        client.target_temperature_max = 50
        client.fan_speed = 3
        yield client
