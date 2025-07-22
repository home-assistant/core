"""Common fixtures for the Ubiquiti airOS tests."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from airos.airos8 import AirOSData
import pytest

from homeassistant.components.airos.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def ap_fixture():
    """Load fixture data for AP mode."""
    json_data = json.loads(load_fixture("airos/ap-ptp.json"))
    return AirOSData.from_dict(json_data)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airos.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airos_client(ap_fixture: dict[str, Any]):
    """Fixture to mock the AirOS API client."""
    with patch(
        "homeassistant.components.airos.AirOS", autospec=True
    ) as mock_airos_class:
        mock_client_instance = mock_airos_class.return_value
        mock_client_instance.login.return_value = True
        mock_client_instance.status.return_value = ap_fixture
        yield mock_airos_class


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the AirOS mocked config entry."""
    return MockConfigEntry(
        title="NanoStation",
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_USERNAME: "ubnt",
        },
        unique_id="device0123",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the AirOS integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
