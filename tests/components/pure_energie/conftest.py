"""Fixtures for Pure Energie integration tests."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pure_energie import Device, SmartMeter
import pytest

from homeassistant.components.pure_energie.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="home",
        domain=DOMAIN,
        data={CONF_HOST: "example"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_pure_energie():
    """Return a mocked Pure Energie client."""
    with patch(
        "homeassistant.components.pure_energie.PureEnergie"
    ) as pure_energie_mock:
        client = pure_energie_mock.return_value
        client.smartmeter = AsyncMock(
            return_value=SmartMeter.from_dict(
                json.loads(load_fixture("pure_energie/smartmeter.json"))
            )
        )
        client.device = AsyncMock(
            return_value=Device.from_dict(
                json.loads(load_fixture("pure_energie/device.json"))
            )
        )
        yield pure_energie_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pure_energie: MagicMock,
) -> MockConfigEntry:
    """Set up the Pure Energie integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
