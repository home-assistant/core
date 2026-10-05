"""Test the Daikin Onecta coordinator."""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from daikin_onecta import OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.rate_limit import RateLimit
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
        assert not coordinator._in_between(time(7, 0, 0), start, end)
        assert coordinator._in_between(time(8, 0, 0), start, end)
        assert coordinator._in_between(time(9, 0, 0), start, end)
        assert not coordinator._in_between(time(10, 0, 0), start, end)
        assert not coordinator._in_between(time(11, 0, 0), start, end)

    def test_in_between_overnight_range(self, coordinator):
        """Time within a range that crosses midnight."""
        start = time(22, 0, 0)
        end = time(7, 0, 0)
        assert coordinator._in_between(time(6, 0, 0), start, end)
        assert not coordinator._in_between(time(7, 0, 0), start, end)
        assert not coordinator._in_between(time(12, 0, 0), start, end)
        assert coordinator._in_between(time(22, 0, 0), start, end)
        assert coordinator._in_between(time(23, 0, 0), start, end)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_high_scan_interval(self, mock_now, coordinator, mock_hass):
        """High scan interval should apply during high-frequency window."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0, 0)

        expected = timedelta(minutes=13)
        result = coordinator._determine_update_interval(mock_hass)
        assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_low_scan_interval(self, mock_now, coordinator, mock_hass):
        """Low scan interval should apply outside transition windows."""
        mock_now.return_value = datetime(2023, 1, 1, 23, 0, 0)

        with patch.object(coordinator, "_in_between", side_effect=[False, False]):
            expected = timedelta(minutes=47)
            result = coordinator._determine_update_interval(mock_hass)
            assert result == expected

    @pytest.mark.parametrize(
        ("now", "options", "expected"),
        [
            (
                datetime(2023, 1, 1, 7, 59),
                {
                    "low_scan_interval": 240,
                    "high_scan_interval": 5,
                    "high_scan_start": "08:00:00",
                    "low_scan_start": "09:00:00",
                },
                timedelta(minutes=5),
            ),
            (
                datetime(2023, 1, 1, 8, 58),
                {
                    "low_scan_interval": 240,
                    "high_scan_interval": 5,
                    "high_scan_start": "08:00:00",
                    "low_scan_start": "09:00:00",
                },
                timedelta(minutes=5),
            ),
            (
                datetime(2023, 1, 1, 21, 59),
                {
                    "low_scan_interval": 240,
                    "high_scan_interval": 5,
                    "high_scan_start": "22:00:00",
                    "low_scan_start": "07:00:00",
                },
                timedelta(minutes=5),
            ),
            (
                datetime(2023, 1, 1, 6, 58),
                {
                    "low_scan_interval": 240,
                    "high_scan_interval": 5,
                    "high_scan_start": "22:00:00",
                    "low_scan_start": "07:00:00",
                },
                timedelta(minutes=5),
            ),
            (
                datetime(2023, 1, 1, 7, 59, 59, 500000),
                {
                    "low_scan_interval": 240,
                    "high_scan_interval": 5,
                    "high_scan_start": "08:00:00",
                    "low_scan_start": "09:00:00",
                },
                timedelta(minutes=5),
            ),
        ],
    )
    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_is_capped_at_window_boundary(
        self, mock_now, coordinator, mock_hass, now, options, expected
    ):
        """Use at least the high-frequency interval near a window boundary."""
        mock_now.return_value = now
        coordinator.options = options

        assert coordinator._determine_update_interval(mock_hass) == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_uses_utc_delay_across_dst_start(
        self, mock_now, coordinator, mock_hass
    ):
        """Use the next boundary's UTC offset when daylight saving time starts."""
        amsterdam = ZoneInfo("Europe/Amsterdam")
        mock_now.return_value = datetime(2026, 3, 28, 23, 30, tzinfo=amsterdam)
        coordinator.options = {
            "low_scan_interval": 240,
            "high_scan_interval": 5,
            "high_scan_start": "03:00:00",
            "low_scan_start": "22:00:00",
        }

        with patch(
            "homeassistant.components.daikin_onecta.coordinator.dt_util.DEFAULT_TIME_ZONE",
            amsterdam,
        ):
            assert coordinator._determine_update_interval(mock_hass) == timedelta(
                minutes=150
            )

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    @patch("homeassistant.components.daikin_onecta.coordinator.random")
    def test_transition_period_randomization(
        self, mock_random, mock_now, coordinator, mock_hass
    ):
        """During transition, interval is randomized between floor and low interval."""
        mock_now.return_value = datetime(2023, 1, 1, 22, 5, 0)
        mock_random.randint.return_value = 120  # 2 minutes

        with patch.object(coordinator, "_in_between", side_effect=[False, True]):
            expected = timedelta(minutes=13)
            result = coordinator._determine_update_interval(mock_hass)
            assert result == expected
            mock_random.randint.assert_called_once_with(60, 2820)

    async def test_rate_limit_uses_update_failed_retry_after(
        self, caplog, coordinator, mock_config_entry
    ):
        """A Daikin rate limit should use the coordinator retry-after mechanism."""
        daikin_api = coordinator.api
        daikin_api.last_patch_call = None
        daikin_api.get_cloud_device_details = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=3060),
                method="GET",
                path="/v1/gateway-devices",
            )
        )
        initial_interval = coordinator.update_interval

        # Simulate daily rate limit reached
        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value.retry_after == EXPECTED_RATE_LIMIT_RETRY_AFTER
        assert exc_info.value.translation_key == "rate_limit_exceeded"
        assert coordinator.update_interval == initial_interval
        assert (
            "Daikin API rate limit reached; retrying after 3060 seconds" in caplog.text
        )

    async def test_post_write_cooldown_is_checked_under_cloud_lock(self, coordinator):
        """Keep cached data when a write completes while polling waits for the lock."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=None)

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator.api.get_cloud_device_details.assert_awaited_once_with(
            cooldown=timedelta(seconds=42)
        )
        assert coordinator.update_interval == timedelta(seconds=42)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_recent_write_skips_cloud_polling(self, mock_utcnow, coordinator):
        """Use the configured cooldown before polling after a recent write."""
        mock_utcnow.return_value = datetime(2023, 1, 1, 12, 0)
        coordinator.api.last_patch_call = mock_utcnow.return_value - timedelta(
            seconds=1
        )
        coordinator.api.get_cloud_device_details = AsyncMock()

        assert await coordinator._async_update_data_from_cloud() == {}
        assert coordinator.update_interval == timedelta(seconds=42)
        coordinator.api.get_cloud_device_details.assert_not_awaited()

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_post_write_cooldown_uses_utc_across_dst_rollback(
        self, mock_utcnow, coordinator
    ):
        """Do not extend cooldown when local time moves backward."""
        # In Amsterdam, local time moves from 02:59 CEST back to 02:01 CET here.
        coordinator.api.last_patch_call = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)
        mock_utcnow.return_value = datetime(2026, 10, 25, 1, 1, tzinfo=UTC)
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=[])

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator.api.get_cloud_device_details.assert_awaited_once_with(
            cooldown=timedelta(seconds=42)
        )

    async def test_connection_error_uses_update_failed(self, coordinator):
        """A connection error should mark the coordinator update as failed."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(
            side_effect=OnectaConnectionError(
                EXPECTED_CONNECTION_ERROR,
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert isinstance(exc_info.value.__cause__, OnectaConnectionError)
        assert exc_info.value.translation_key == "connection_failed"

    async def test_missing_cloud_device_is_marked_unavailable(self, coordinator):
        """Mark cached gateways unavailable when the cloud no longer returns them."""
        missing_device = MagicMock()
        coordinator.data = {"missing": missing_device}
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=[])

        await coordinator._async_update_data_from_cloud()

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
            coordinator,
            "_determine_update_interval",
            return_value=timedelta(minutes=45),
        ) as determine:
            assert coordinator.update_settings(updated_entry)

        assert coordinator.options == options
        assert coordinator.update_interval == timedelta(minutes=45)
        determine.assert_called_once_with(mock_hass)

    def test_update_settings_ignores_unchanged_options(
        self, coordinator, mock_config_entry
    ):
        """Do not apply settings when only config-entry data changed."""
        with patch.object(coordinator, "_determine_update_interval") as determine:
            assert not coordinator.update_settings(mock_config_entry)

        assert coordinator.options == POLLING_OPTIONS
        determine.assert_not_called()
