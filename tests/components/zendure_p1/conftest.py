"""Common fixtures for the Zendure Smart Meter P1 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zendure_p1 import Report

from homeassistant.components.zendure_p1.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def mock_client(device_id: str = "SN123456") -> AsyncMock:
    """Create a mock ZendureP1Client for config flow tests."""
    mock_report = MagicMock()
    mock_report.device_id = device_id
    client = AsyncMock()
    client.get_report.return_value = mock_report
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.zendure_p1.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="SN123456",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="SN123456",
    )


@pytest.fixture
def mock_zendure_p1_client() -> Generator[AsyncMock]:
    """Return a mocked ZendureP1Client."""
    with patch(
        "homeassistant.components.zendure_p1.ZendureP1Client",
        autospec=True,
    ) as client_class_mock:
        client = client_class_mock.return_value
        client.get_report = AsyncMock(
            return_value=Report(
                timestamp=1000000,
                device_id="SN123456",
                a_apparent_power=100,
                b_apparent_power=200,
                c_apparent_power=300,
                total_power=600,
            )
        )
        client.close = AsyncMock()
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zendure_p1_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the Zendure Smart Meter P1 integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
