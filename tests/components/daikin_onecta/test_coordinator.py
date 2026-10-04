"""Test the Daikin Onecta coordinator."""

from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import OnectaConnectionError, OnectaRateLimitError
import pytest

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

EXPECTED_RATE_LIMIT_RETRY_AFTER = 3060
EXPECTED_CONNECTION_ERROR = "network unavailable"
POLLING_OPTIONS = {
    "low_scan_interval": 47,
    "high_scan_interval": 13,
    "high_scan_start": "08:00:00",
    "low_scan_start": "20:00:00",
    "scan_ignore": 42,
}


@pytest.fixture
def mock_hass():
    """Return a mocked HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with non-default polling options."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="daikin_onecta",
        unique_id="12345",
        options=POLLING_OPTIONS,
    )


@pytest.fixture
def coordinator(mock_hass, mock_config_entry):
    """Return a coordinator using the configured polling options."""
    mock_config_entry.add_to_hass(mock_hass)
    return OnectaDataUpdateCoordinator(mock_hass, mock_config_entry, MagicMock())


class TestOnectaDataUpdateCoordinator:
    """Test OnectaDataUpdateCoordinator class."""

    def test_in_between_normal_range(self, coordinator):
        """Time within a simple range not crossing midnight."""
        start = time(8, 0, 0)
        end = time(10, 0, 0)
        assert not coordinator.in_between(time(7, 0, 0), start, end)
        assert coordinator.in_between(time(8, 0, 0), start, end)
        assert coordinator.in_between(time(9, 0, 0), start, end)
        assert not coordinator.in_between(time(10, 0, 0), start, end)
        assert not coordinator.in_between(time(11, 0, 0), start, end)

    def test_in_between_overnight_range(self, coordinator):
        """Time within a range that crosses midnight."""
        start = time(22, 0, 0)
        end = time(7, 0, 0)
        assert coordinator.in_between(time(6, 0, 0), start, end)
        assert not coordinator.in_between(time(7, 0, 0), start, end)
        assert not coordinator.in_between(time(12, 0, 0), start, end)
        assert coordinator.in_between(time(22, 0, 0), start, end)
        assert coordinator.in_between(time(23, 0, 0), start, end)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_high_scan_interval(self, mock_now, coordinator, mock_hass):
        """High scan interval should apply during high-frequency window."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0, 0)

        expected = timedelta(minutes=13)
        result = coordinator.determine_update_interval(mock_hass)
        assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_low_scan_interval(self, mock_now, coordinator, mock_hass):
        """Low scan interval should apply outside transition windows."""
        mock_now.return_value = datetime(2023, 1, 1, 23, 0, 0)

        with patch.object(coordinator, "in_between", side_effect=[False, False]):
            expected = timedelta(minutes=47)
            result = coordinator.determine_update_interval(mock_hass)
            assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    @patch("homeassistant.components.daikin_onecta.coordinator.random")
    def test_transition_period_randomization(
        self, mock_random, mock_now, coordinator, mock_hass
    ):
        """During transition, interval is randomized between floor and low interval."""
        mock_now.return_value = datetime(2023, 1, 1, 22, 5, 0)
        mock_random.randint.return_value = 120  # 2 minutes

        with patch.object(coordinator, "in_between", side_effect=[False, True]):
            expected = timedelta(seconds=120)
            result = coordinator.determine_update_interval(mock_hass)
            assert result == expected
            mock_random.randint.assert_called_once_with(60, 2820)

    async def test_rate_limit_uses_update_failed_retry_after(
        self, caplog, coordinator, mock_config_entry
    ):
        """A Daikin rate limit should use the coordinator retry-after mechanism."""
        daikin_api = coordinator.api
        daikin_api.last_patch_call = None
        daikin_api.get_cloud_device_details = AsyncMock(
            side_effect=OnectaRateLimitError(3060)
        )
        initial_interval = coordinator.update_interval

        # Simulate daily rate limit reached
        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator.async_update_data()

        assert exc_info.value.retry_after == EXPECTED_RATE_LIMIT_RETRY_AFTER
        assert coordinator.update_interval == initial_interval
        assert (
            "Daikin API rate limit reached; retrying after 3060 seconds" in caplog.text
        )

    async def test_post_write_cooldown_is_checked_under_cloud_lock(self, coordinator):
        """Keep cached data when a write completes while polling waits for the lock."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=None)

        assert await coordinator.async_update_data() == {}
        coordinator.api.get_cloud_device_details.assert_awaited_once_with(
            cooldown=timedelta(seconds=42)
        )
        assert coordinator.update_interval == timedelta(seconds=42)

    async def test_connection_error_uses_update_failed(self, coordinator):
        """A connection error should mark the coordinator update as failed."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(
            side_effect=OnectaConnectionError(EXPECTED_CONNECTION_ERROR)
        )

        with pytest.raises(
            UpdateFailed, match="Unable to connect to the Daikin API"
        ) as exc_info:
            await coordinator.async_update_data()

        assert isinstance(exc_info.value.__cause__, OnectaConnectionError)

    async def test_missing_cloud_device_is_marked_unavailable(self, coordinator):
        """Mark cached gateways unavailable when the cloud no longer returns them."""
        missing_device = MagicMock()
        coordinator.data = {"missing": missing_device}
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=[])

        await coordinator.async_update_data()

        missing_device.mark_unavailable.assert_called_once_with()

    def test_update_settings(self, coordinator, mock_config_entry, mock_hass):
        """Apply changed polling options to the coordinator."""
        options = {
            "low_scan_interval": 45,
            "high_scan_interval": 15,
            "high_scan_start": "07:00:00",
            "low_scan_start": "22:00:00",
        }
        updated_entry = MockConfigEntry(
            domain=DOMAIN, title="daikin_onecta", unique_id="12345", options=options
        )

        with patch.object(
            coordinator, "determine_update_interval", return_value=timedelta(minutes=45)
        ) as determine:
            coordinator.update_settings(updated_entry)

        assert coordinator.options == options
        assert coordinator.update_interval == timedelta(minutes=45)
        determine.assert_called_once_with(mock_hass)
