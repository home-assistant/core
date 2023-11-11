"""Common fixtures for the Hydrawise tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hydrawise.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pydrawise(
    mock_controller: dict[str, Any],
    mock_zones: list[dict[str, Any]],
) -> Generator[Mock, None, None]:
    """Mock LegacyHydrawise."""
    with patch("pydrawise.legacy.LegacyHydrawise", autospec=True) as mock_pydrawise:
        mock_pydrawise.return_value.controller_info = {"controllers": [mock_controller]}
        mock_pydrawise.return_value.current_controller = mock_controller
        mock_pydrawise.return_value.controller_status = {"relays": mock_zones}
        mock_pydrawise.return_value.relays = mock_zones
        mock_pydrawise.return_value.relays_by_zone_number = {
            r["relay"]: r for r in mock_zones
        }
        yield mock_pydrawise.return_value


@pytest.fixture
def mock_controller() -> dict[str, Any]:
    """Mock Hydrawise controller."""
    return {
        "name": "Home Controller",
        "last_contact": 1693292420,
        "serial_number": "0310b36090",
        "controller_id": 52496,
        "status": "Unknown",
    }


@pytest.fixture
def mock_zones() -> list[dict[str, Any]]:
    """Mock Hydrawise zones."""
    return [
        {
            "name": "Zone One",
            "period": 259200,
            "relay": 1,
            "relay_id": 5965394,
            "run": 1800,
            "stop": 1,
            "time": 330597,
            "timestr": "Sat",
            "type": 1,
        },
        {
            "name": "Zone Two",
            "period": 259200,
            "relay": 2,
            "relay_id": 5965395,
            "run": 1788,
            "stop": 1,
            "time": 1,
            "timestr": "Now",
            "type": 106,
        },
    ]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "abc123",
        },
        unique_id="hydrawise-customerid",
    )


@pytest.fixture
async def mock_added_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pydrawise: Mock,
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.config_entries.async_domains()
    return mock_config_entry
