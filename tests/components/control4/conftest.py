"""Fixtures for Control4 tests."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.control4.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            "controller_unique_id": "control4_test_00AA00AA00AA",
        },
        options={CONF_SCAN_INTERVAL: 5},
        unique_id="control4_test_00AA00AA00AA",
        title="Control4",
    )


@pytest.fixture
def mock_director_all_items():
    """Return mock director items."""
    return [
        {
            "id": 123,
            "name": "Residential Thermostat V2",
            "type": 1,
            "parentId": 456,
            "categories": ["comfort"],
        },
        {
            "id": 456,
            "manufacturer": "Control4",
            "roomName": "Studio",
            "model": "C4-TSTAT",
        },
    ]


@pytest.fixture
def mock_director_variables():
    """Return mock thermostat variable data."""
    return {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Heat",
            "TEMPERATURE_F": 72.5,
            "HUMIDITY": 45,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }


@pytest.fixture
def mock_director(mock_director_all_items):
    """Mock C4Director."""
    director = MagicMock()
    director.getAllItemInfo = AsyncMock(
        return_value=json.dumps(mock_director_all_items)
    )
    director.getAllItemVariableValue = AsyncMock(return_value={})
    director.getItemVariableValue = AsyncMock(return_value=None)
    return director


@pytest.fixture
def mock_account():
    """Mock C4Account."""
    account = MagicMock()
    account.getAccountBearerToken = AsyncMock()
    account.getAccountControllers = AsyncMock(
        return_value={"href": "https://example.com/controller"}
    )
    account.getDirectorBearerToken = AsyncMock(return_value={"token": "test-token"})
    account.getControllerOSVersion = AsyncMock(return_value="3.2.0")
    return account


@pytest.fixture
def platforms() -> list[str]:
    """Platforms to test."""
    return ["climate"]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_director: MagicMock,
    mock_account: MagicMock,
    mock_director_variables: dict,
    platforms: list[str],
) -> MockConfigEntry:
    """Set up the Control4 integration for testing."""
    mock_config_entry.add_to_hass(hass)

    async def mock_update_variables(*args, **kwargs):
        """Mock update variables function."""
        return mock_director_variables

    with (
        patch(
            "homeassistant.components.control4.C4Account",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.control4.C4Director",
            return_value=mock_director,
        ),
        patch(
            "homeassistant.components.control4.director_utils.update_variables_for_config_entry",
            new=mock_update_variables,
        ),
        patch(
            "homeassistant.components.control4.PLATFORMS",
            platforms,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
