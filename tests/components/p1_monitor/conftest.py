"""Fixtures for P1 Monitor integration tests."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from p1monitor import Phases, Settings, SmartMeter, WaterMeter
import pytest

from homeassistant.components.p1_monitor.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="monitor",
        domain=DOMAIN,
        data={CONF_HOST: "example"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_p1monitor():
    """Return a mocked P1 Monitor client."""
    with patch("homeassistant.components.p1_monitor.P1Monitor") as p1monitor_mock:
        client = p1monitor_mock.return_value
        client.smartmeter = AsyncMock(
            return_value=SmartMeter.from_dict(
                json.loads(load_fixture("p1_monitor/smartmeter.json"))
            )
        )
        client.phases = AsyncMock(
            return_value=Phases.from_dict(
                json.loads(load_fixture("p1_monitor/phases.json"))
            )
        )
        client.settings = AsyncMock(
            return_value=Settings.from_dict(
                json.loads(load_fixture("p1_monitor/settings.json"))
            )
        )
        client.watermeter = AsyncMock(
            return_value=WaterMeter.from_dict(
                json.loads(load_fixture("p1_monitor/watermeter.json"))
            )
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_p1monitor: MagicMock
) -> MockConfigEntry:
    """Set up the P1 Monitor integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
