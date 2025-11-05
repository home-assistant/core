"""Fixtures for the Roomba tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from roombapy import Roomba

from homeassistant.components.roomba import CONF_BLID, CONF_CONTINUOUS, DOMAIN
from homeassistant.const import CONF_DELAY, CONF_HOST, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.0.30",
            CONF_BLID: "blid123",
            CONF_PASSWORD: "pass123",
        },
        options={
            CONF_CONTINUOUS: True,
            CONF_DELAY: 10,
        },
        unique_id="blid123",
    )


@pytest.fixture
def mock_roomba() -> Generator[AsyncMock]:
    """Build a fixture for the 17Track API."""
    mock_roomba = AsyncMock(spec=Roomba, autospec=True)
    mock_roomba.master_state = {
        "state": {
            "reported": {
                "cap": {"pose": 1},
                "cleanMissionStatus": {"cycle": "none", "phase": "charge"},
                "pose": {"point": {"x": 1, "y": 2}, "theta": 90},
                "dock": {"tankLvl": 99},
                "hwPartsRev": {
                    "navSerialNo": "12345",
                    "wlan0HwAddr": "AA:BB:CC:DD:EE:FF",
                },
                "sku": "980",
                "name": "Test Roomba",
                "softwareVer": "3.2.1",
                "hardwareRev": "1.0",
                "bin": {"present": True, "full": False},
            }
        }
    }
    mock_roomba.roomba_connected = True

    with patch(
        "homeassistant.components.roomba.RoombaFactory.create_roomba",
        return_value=mock_roomba,
    ):
        yield mock_roomba
