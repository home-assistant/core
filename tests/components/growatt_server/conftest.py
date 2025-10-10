"""Common fixtures for the Growatt server tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_URL,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_growatt_v1_api():
    """Return a mocked Growatt V1 API.

    This fixture provides the happy path for integration setup and basic operations.
    Individual tests can override specific return values to test error conditions.

    Methods mocked for integration setup:
    - device_list: Called during async_setup_entry to discover devices
    - plant_energy_overview: Called by total coordinator during first refresh

    Methods mocked for MIN device coordinator refresh:
    - min_detail: Provides device state (e.g., acChargeEnable for switches)
    - min_settings: Provides settings (e.g. TOU periods)
    - min_energy: Provides energy data (empty for switch tests, sensors need real data)

    Methods mocked for switch operations:
    - min_write_parameter: Called by switch entities to change settings
    """
    with patch("growattServer.OpenApiV1", autospec=True) as mock_v1_api_class:
        mock_v1_api = mock_v1_api_class.return_value

        # Called during setup to discover devices
        mock_v1_api.device_list.return_value = {
            "devices": [
                {
                    "device_sn": "MIN123456",
                    "type": 7,  # MIN device type
                }
            ]
        }

        # Called by MIN device coordinator during refresh
        mock_v1_api.min_detail.return_value = {
            "deviceSn": "MIN123456",
            "acChargeEnable": 1,  # AC charge enabled - read by switch entity
        }

        # Called by MIN device coordinator during refresh
        mock_v1_api.min_settings.return_value = {
            # Forced charge time segments (not used by switch, but coordinator fetches it)
            "forcedTimeStart1": "06:00",
            "forcedTimeStop1": "08:00",
            "forcedChargeBatMode1": 1,
            "forcedChargeFlag1": 1,
            "forcedTimeStart2": "22:00",
            "forcedTimeStop2": "24:00",
            "forcedChargeBatMode2": 0,
            "forcedChargeFlag2": 0,
        }

        # Called by MIN device coordinator during refresh
        # Empty dict is sufficient for switch tests (sensor tests would need real energy data)
        mock_v1_api.min_energy.return_value = {}

        # Called by total coordinator during refresh
        mock_v1_api.plant_energy_overview.return_value = {
            "today_energy": 12.5,
            "total_energy": 1250.0,
            "current_power": 2500,
        }

        # Called by switch entities during turn_on/turn_off
        mock_v1_api.min_write_parameter.return_value = None

        yield mock_v1_api


@pytest.fixture
def mock_growatt_classic_api():
    """Return a mocked Growatt Classic API.

    This fixture provides the happy path for Classic API integration setup.
    Individual tests can override specific return values to test error conditions.

    Methods mocked for integration setup:
    - login: Called during get_device_list_classic to authenticate
    - plant_list: Called during setup if plant_id is default (to auto-select plant)
    - device_list: Called during async_setup_entry to discover devices

    Methods mocked for total coordinator refresh:
    - plant_info: Provides plant totals (energy, power, money) for Classic API

    Methods mocked for device-specific tests:
    - tlx_detail: Provides TLX device data (kept for potential future tests)
    """
    with patch("growattServer.GrowattApi", autospec=True) as mock_classic_api_class:
        # Use the autospec'd mock instance instead of creating a new Mock()
        mock_classic_api = mock_classic_api_class.return_value

        # Called during setup to authenticate with Classic API
        mock_classic_api.login.return_value = {"success": True, "user": {"id": 12345}}

        # Called during setup if plant_id is default (auto-select first plant)
        mock_classic_api.plant_list.return_value = {"data": [{"plantId": "12345"}]}

        # Called during setup to discover devices
        mock_classic_api.device_list.return_value = [
            {"deviceSn": "MIN123456", "deviceType": "min"}
        ]

        # Called by total coordinator during refresh for Classic API
        mock_classic_api.plant_info.return_value = {
            "deviceList": [],
            "totalEnergy": 1250.0,
            "todayEnergy": 12.5,
            "invTodayPpv": 2500,
            "plantMoneyText": "123.45/USD",
        }

        # Called for TLX device coordinator (kept for potential future tests)
        mock_classic_api.tlx_detail.return_value = {
            "data": {
                "deviceSn": "TLX123456",
            }
        }

        yield mock_classic_api


@pytest.fixture
def mock_config_entry():
    """Return the default mocked config entry (V1 API with token auth).

    This is the primary config entry used by most tests. For Classic API tests,
    use mock_config_entry_classic instead.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_API_TOKEN,
            CONF_TOKEN: "test_token_123",
            CONF_URL: DEFAULT_URL,
            "user_id": "12345",
            CONF_PLANT_ID: "plant_123",
            "name": "Test Plant",
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_config_entry_classic():
    """Return a mocked config entry for Classic API (password auth).

    Use this for tests that specifically need to test Classic API behavior.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: DEFAULT_URL,
            CONF_PLANT_ID: "12345",
            "name": "Test Plant",
        },
        unique_id="12345",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_growatt_v1_api
) -> MockConfigEntry:
    """Set up the Growatt Server integration for testing (V1 API).

    This combines mock_config_entry and mock_growatt_v1_api to provide a fully
    initialized integration ready for testing. Use @pytest.mark.usefixtures("init_integration")
    to automatically set up the integration before your test runs.

    For Classic API tests, manually set up using mock_config_entry_classic and
    mock_growatt_classic_api instead.
    """
    # The mock_growatt_v1_api fixture is required for patches to be active
    assert mock_growatt_v1_api is not None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
