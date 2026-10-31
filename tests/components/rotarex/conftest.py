"""Common fixtures for the Rotarex tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from rotarex_dimes_srg_api import RotarexSyncData, RotarexTank

from homeassistant.components.rotarex.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rotarex.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        unique_id="test@example.com",
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test_password"},
    )


@pytest.fixture
def mock_rotarex_api() -> Generator[AsyncMock]:
    """Mock a RotarexApi client."""
    with (
        patch(
            "homeassistant.components.rotarex.coordinator.RotarexApi", autospec=True
        ) as rotarex_api,
        patch(
            "homeassistant.components.rotarex.config_flow.RotarexApi", new=rotarex_api
        ),
    ):
        api = rotarex_api.return_value
        api.fetch_tanks.return_value = [
            RotarexTank(
                guid="tank1-guid",
                name="Tank 1",
                synch_datas=[
                    RotarexSyncData(
                        synch_date=datetime(2024, 1, 1, 12, 0),
                        level=75.5,
                        battery=85.0,
                    ),
                    RotarexSyncData(
                        synch_date=datetime(2024, 1, 2, 12, 0),
                        level=70.0,
                        battery=80.0,
                    ),
                ],
            ),
            RotarexTank(
                guid="tank2-guid",
                name="Tank 2",
                synch_datas=[
                    RotarexSyncData(
                        synch_date=datetime(2024, 1, 1, 12, 0),
                        level=50.0,
                        battery=90.0,
                    ),
                ],
            ),
        ]
        yield api
