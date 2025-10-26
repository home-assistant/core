"""Configuration for Saunum Leil integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysaunum import SaunumData
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        title="Saunum Leil Sauna",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
        },
        unique_id="192.168.1.100:502",
    )


@pytest.fixture
def mock_saunum_client() -> Generator[MagicMock]:
    """Return a mocked Saunum client for config flow and integration tests."""
    with (
        patch(
            "homeassistant.components.saunum.config_flow.SaunumClient"
        ) as mock_client_class,
        patch("homeassistant.components.saunum.SaunumClient") as mock_client_class2,
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client.close = MagicMock()
        mock_client.is_connected = True

        # Create mock data for async_get_data
        mock_data = SaunumData(
            session_active=False,
            sauna_type=0,
            sauna_duration=120,
            fan_duration=10,
            target_temperature=80,
            fan_speed=2,
            light_on=False,
            current_temperature=75.0,
            on_time=3600,
            heater_elements_active=0,
            door_open=False,
            alarm_door_open=False,
            alarm_door_sensor=False,
            alarm_thermal_cutoff=False,
            alarm_internal_temp=False,
            alarm_temp_sensor_short=False,
            alarm_temp_sensor_open=False,
        )

        mock_client.async_get_data = AsyncMock(return_value=mock_data)
        mock_client.async_start_session = AsyncMock()
        mock_client.async_stop_session = AsyncMock()
        mock_client.async_set_target_temperature = AsyncMock()

        # Make both patches return the same mock
        mock_client_class.return_value = mock_client
        mock_client_class2.return_value = mock_client

        yield mock_client


# Backward compatibility aliases
@pytest.fixture
def mock_modbus_client(mock_saunum_client) -> MagicMock:
    """Alias for mock_saunum_client for backward compatibility."""
    return mock_saunum_client


@pytest.fixture
def mock_modbus_coordinator(mock_saunum_client) -> MagicMock:
    """Alias for mock_saunum_client for backward compatibility."""
    return mock_saunum_client


@pytest.fixture
def mock_setup_platforms():
    """Mock async_forward_entry_setups."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_setup:
        mock_setup.return_value = True
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_saunum_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
