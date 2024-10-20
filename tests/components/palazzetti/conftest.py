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
        client.mac = AsyncMock(return_value="11:22:33:44:55:66")
        client.name = AsyncMock(return_value="Stove")
        client.sw_version = AsyncMock(return_value="0.0.0")
        client.hw_version = AsyncMock(return_value="1.1.1")
        client.fan_speed_min = AsyncMock(return_value=1)
        client.fan_speed_max = AsyncMock(return_value=5)
        client.has_fan_silent = AsyncMock(return_value=False)
        client.has_fan_high = AsyncMock(return_value=True)
        client.has_fan_auto = AsyncMock(return_value=True)
        client.has_on_off_switch = AsyncMock(return_value=True)
        client.connected = AsyncMock(return_value=True)
        client.is_heating = AsyncMock(return_value=True)
        client.room_temperature = AsyncMock(18)
        client.target_temperature = AsyncMock(21)
        client.fan_speed = AsyncMock(3)
        yield client
