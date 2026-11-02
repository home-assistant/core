"""Common fixtures for the Antifurto365 iAlarm tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pyasyncialarm import IAlarm
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ialarm.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

TEST_MAC = "00:00:54:12:34:56"


@pytest.fixture(name="ialarm_api")
def ialarm_api_fixture() -> Generator[MagicMock]:
    """Set up IAlarm API fixture."""
    with patch("homeassistant.components.ialarm.IAlarm") as mock_ialarm_api:
        client = mock_ialarm_api.return_value
        client.host = "192.168.10.20"
        client.get_mac = AsyncMock(return_value=TEST_MAC)
        client.get_status = AsyncMock(
            return_value={"status_value": IAlarm.DISARMED, "alarmed_zones": []}
        )
        client.arm_away = AsyncMock()
        client.arm_stay = AsyncMock()
        client.disarm = AsyncMock(return_value=IAlarm.DISARMED)
        client.shutdown = AsyncMock()
        yield mock_ialarm_api


@pytest.fixture(name="mock_config_entry")
def mock_config_fixture() -> MockConfigEntry:
    """Return a fake config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.10.20", CONF_PORT: 18034},
        entry_id=str(uuid4()),
    )
