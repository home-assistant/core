"""Common fixtures for the SolarEdge Modules tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from solaredge_web import EnergyData

from homeassistant.components.solaredge_modules.const import CONF_SITE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solaredge_modules.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        title="SolarEdge Modules",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SITE_ID: "123456",
        },
        unique_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_solar_edge_web() -> Generator[AsyncMock]:
    """Mock SolarEdgeWeb."""
    with (
        patch(
            "homeassistant.components.solaredge_modules.coordinator.SolarEdgeWeb",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.solaredge_modules.config_flow.SolarEdgeWeb",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.async_get_equipment.return_value = {
            1001: {"displayName": "1.1"},
            1002: {"displayName": "1.2"},
        }
        api.async_get_energy_data.return_value = [
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 0)),
                values={1001: 10.0, 1002: 20.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 15)),
                values={1001: 11.0, 1002: 21.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 30)),
                values={1001: 12.0, 1002: 22.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 45)),
                values={1001: 13.0, 1002: 23.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 0)),
                values={1001: 14.0, 1002: 24.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 15)),
                values={1001: 15.0, 1002: 25.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 30)),
                values={1001: 16.0, 1002: 26.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 45)),
                values={1001: 17.0, 1002: 27.0},
            ),
        ]

        yield api
