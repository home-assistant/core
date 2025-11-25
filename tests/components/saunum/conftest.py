"""Configuration for Saunum Leil integration tests."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from pysaunum import SaunumData
import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def patch_delayed_refresh_seconds() -> Generator[None]:
    """Patch DELAYED_REFRESH_SECONDS to 0 to avoid delays in tests."""
    with patch(
        "homeassistant.components.saunum.climate.DELAYED_REFRESH_SECONDS",
        timedelta(seconds=0),
    ):
        yield


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE, Platform.LIGHT]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="01K98T2T85R5GN0ZHYV25VFMMA",
        title="Saunum Leil Sauna",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
    )


@pytest.fixture
def mock_saunum_client() -> Generator[MagicMock]:
    """Return a mocked Saunum client for config flow and integration tests."""
    with (
        patch(
            "homeassistant.components.saunum.config_flow.SaunumClient", autospec=True
        ) as mock_client_class,
        patch("homeassistant.components.saunum.SaunumClient", new=mock_client_class),
    ):
        mock_client = mock_client_class.return_value
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

        mock_client.async_get_data.return_value = mock_data

        yield mock_client


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


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock Saunum setup entry."""
    with patch(
        "homeassistant.components.saunum.async_setup_entry", autospec=True
    ) as mock_setup_entry:
        mock_setup_entry.return_value = True
        yield mock_setup_entry
