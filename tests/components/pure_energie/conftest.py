"""Fixtures for Pure Energie integration tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from gridnet import Device as GridNetDevice, SmartBridge
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
        data={CONF_HOST: "192.168.1.123"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.pure_energie.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_pure_energie_config_flow() -> Generator[MagicMock]:
    """Return a mocked Pure Energie client."""
    with patch(
        "homeassistant.components.pure_energie.config_flow.GridNet", autospec=True
    ) as pure_energie_mock:
        pure_energie = pure_energie_mock.return_value
        pure_energie.device.return_value = GridNetDevice.from_dict(
            json.loads(load_fixture("device.json", DOMAIN))
        )
        yield pure_energie


@pytest.fixture
def mock_pure_energie():
    """Return a mocked Pure Energie client."""
    with patch(
        "homeassistant.components.pure_energie.coordinator.GridNet", autospec=True
    ) as pure_energie_mock:
        pure_energie = pure_energie_mock.return_value
        pure_energie.smartbridge = AsyncMock(
            return_value=SmartBridge.from_dict(
                json.loads(load_fixture("pure_energie/smartbridge.json"))
            )
        )
        pure_energie.device = AsyncMock(
            return_value=GridNetDevice.from_dict(
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
