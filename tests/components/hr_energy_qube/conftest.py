"""Common fixtures for the Qube Heat Pump tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from python_qube_heatpump.models import QubeState

from homeassistant.components.hr_energy_qube.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hr_energy_qube.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_qube_client() -> Generator[MagicMock]:
    """Mock the QubeClient for both integration and config flow."""
    with (
        patch(
            "homeassistant.components.hr_energy_qube.QubeClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.hr_energy_qube.config_flow.QubeClient",
            new=mock_client_cls,
        ),
    ):
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)
        client.is_connected = True
        client.close = AsyncMock(return_value=None)
        client.async_get_software_version = AsyncMock(return_value="2.15")

        state = QubeState()
        state.temp_supply = 45.0
        state.temp_return = 40.0
        state.temp_outside = 10.0
        state.temp_source_in = 8.0
        state.temp_source_out = 12.0
        state.temp_room = 21.0
        state.temp_dhw = 50.0
        state.power_thermic = 5000.0
        state.power_electric = 1200.0
        state.energy_total_electric = 123.456
        state.energy_total_thermic = 500.0
        state.cop_calc = 4.2
        state.compressor_speed = 3000.0
        state.flow_rate = 15.5
        state.setpoint_room_heat_day = 21.0
        state.setpoint_room_heat_night = 18.0
        state.setpoint_room_cool_day = 25.0
        state.setpoint_room_cool_night = 23.0
        state.status_code = 1

        client.get_all_data = AsyncMock(return_value=state)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 502},
        title="Qube heat pump",
        entry_id="01JQUBEHEATPUMP00000000000",
    )
