"""Common fixtures for the Zinvolt tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from zinvolt.models import BatteryListResponse, BatteryState

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import TOKEN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.zinvolt.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@test.com",
        unique_id="a0226b8f-98fe-4524-b369-272b466b8797",
        data={CONF_ACCESS_TOKEN: TOKEN},
    )


@pytest.fixture
def mock_zinvolt_client() -> Generator[AsyncMock]:
    """Mock Zinvolt client."""
    with (
        patch(
            "homeassistant.components.zinvolt.ZinvoltClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.zinvolt.config_flow.ZinvoltClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = TOKEN
        client.get_batteries.return_value = BatteryListResponse.from_json(
            load_fixture("batteries.json", DOMAIN)
        ).batteries
        client.get_battery_status.return_value = BatteryState.from_json(
            load_fixture("current_state.json", DOMAIN)
        )
        yield client
