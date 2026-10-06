"""Test the Daikin Onecta coordinator."""

from datetime import UTC, datetime, time, timedelta
from math import ceil
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from daikin_onecta import OnectaApiError, OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.rate_limit import RateLimit
import pytest

from homeassistant.components.daikin_onecta import coordinator as coordinator_module
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

EXPECTED_RATE_LIMIT_RETRY_AFTER = 3060
EXPECTED_CONNECTION_ERROR = "network unavailable"


def test_device_update_refreshes_cached_name() -> None:
    """Use the replacement cloud model's name in device-registry metadata."""
    device = DaikinOnectaDevice(
        SimpleNamespace(
            id="gateway",
            display_name="Old name",
            available=True,
            mac_address=None,
            device_model=None,
            gateway_embedded_id=None,
        )
    )

    device.set_device_data(
        SimpleNamespace(
            id="gateway",
            display_name="New name",
            available=True,
            mac_address=None,
            device_model=None,
            gateway_embedded_id=None,
        )
    )

    assert device.name == "New name"


def _patch_polling_schedule(
    *,
    low_interval: int = 240,
    high_interval: int = 5,
    high_start: time,
    low_start: time,
):
    """Patch fixed polling defaults for boundary tests."""
    return patch.multiple(
        coordinator_module,
        _LOW_SCAN_INTERVAL=timedelta(minutes=low_interval),
        _HIGH_SCAN_INTERVAL=timedelta(minutes=high_interval),
        _HIGH_SCAN_START=high_start,
        _LOW_SCAN_START=low_start,
    )


@pytest.fixture
def mock_hass():
    """Return a mocked HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="daikin_onecta",
        unique_id="12345",
        options={},
    )


@pytest.fixture
def coordinator(mock_hass, mock_config_entry):
    """Return a coordinator."""
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
    def test_high_scan_interval(self, mock_now, coordinator):
        """High scan interval should apply during high-frequency window."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0, 0)

        expected = timedelta(seconds=594)
        result = coordinator._determine_update_interval()
        assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_low_scan_interval(self, mock_now, coordinator):
        """Low scan interval should apply outside transition windows."""
        mock_now.return_value = datetime(2023, 1, 1, 23, 0, 0)

        with patch.object(coordinator, "_in_between", side_effect=[False, False]):
            expected = timedelta(seconds=1782)
            result = coordinator._determine_update_interval()
            assert result == expected

    def test_polling_intervals_use_default_daily_limit(self, coordinator):
        """Use no more than 55% of the conservative default daily limit."""
        coordinator.api.rate_limits = {"day": None}

        high_interval, low_interval = coordinator._polling_intervals()

        assert high_interval == timedelta(seconds=594)
        assert low_interval == timedelta(seconds=1782)
        assert ceil(15 * 3600 / 594) + ceil(9 * 3600 / 1782) == 110

    def test_polling_intervals_use_reported_daily_limit(self, coordinator):
        """Adapt the polling budget when Daikin reports a different limit."""
        coordinator.api.rate_limits = {"day": 400}

        assert coordinator._polling_intervals() == (
            timedelta(seconds=296),
            timedelta(seconds=888),
        )

    def test_polling_intervals_cap_a_1000_daily_limit(self, coordinator):
        """Keep a 1000-call daily limit at the three-minute polling floor."""
        coordinator.api.rate_limits = {"day": 1000}

        assert coordinator._polling_intervals() == (
            timedelta(minutes=3),
            timedelta(minutes=9),
        )

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    async def test_cloud_response_updates_polling_interval_from_daily_limit(
        self, mock_now, coordinator
    ):
        """Apply Daikin's reported daily limit after a cloud refresh."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0)
        coordinator.api.last_patch_call = None
        coordinator.api.rate_limits = {"day": 400}
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=[])

        await coordinator._async_update_data_from_cloud()

        assert coordinator.update_interval == timedelta(seconds=296)

    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            (
                datetime(2023, 1, 1, 6, 59),
                timedelta(seconds=594),
            ),
            (
                datetime(2023, 1, 1, 21, 59),
                timedelta(seconds=594),
            ),
            (
                datetime(2023, 1, 1, 6, 59, 59, 500000),
                timedelta(seconds=594),
            ),
        ],
    )
    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_is_capped_at_window_boundary(
        self, mock_now, coordinator, now, expected
    ):
        """Use at least the high-frequency interval near a window boundary."""
        mock_now.return_value = now
        assert coordinator._determine_update_interval() == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_uses_utc_delay_across_dst_start(self, mock_now, coordinator):
        """Use the next boundary's UTC offset when daylight saving time starts."""
        amsterdam = ZoneInfo("Europe/Amsterdam")
        mock_now.return_value = datetime(2026, 3, 28, 23, 30, tzinfo=amsterdam)
        with (
            _patch_polling_schedule(high_start=time(3), low_start=time(22)),
            patch(
                "homeassistant.components.daikin_onecta.coordinator.dt_util.DEFAULT_TIME_ZONE",
                amsterdam,
            ),
        ):
            assert coordinator._determine_update_interval() == timedelta(minutes=150)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_uses_clock_transition_for_nonexistent_boundary(
        self, mock_now, coordinator
    ):
        """Poll at the DST jump when it begins the high-frequency window."""
        amsterdam = ZoneInfo("Europe/Amsterdam")
        mock_now.return_value = datetime(2026, 3, 29, 1, 59, tzinfo=amsterdam)
        with (
            _patch_polling_schedule(high_start=time(2, 30), low_start=time(3, 15)),
            patch(
                "homeassistant.components.daikin_onecta.coordinator.dt_util.DEFAULT_TIME_ZONE",
                amsterdam,
            ),
        ):
            assert coordinator._determine_update_interval() == timedelta(minutes=3)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_preserves_dst_fold_at_window_boundary(
        self, mock_now, coordinator
    ):
        """Use the second occurrence of a boundary during daylight saving rollback."""
        amsterdam = ZoneInfo("Europe/Amsterdam")
        mock_now.return_value = datetime(2026, 10, 25, 2, 15, tzinfo=amsterdam, fold=1)
        with (
            _patch_polling_schedule(high_start=time(2, 30), low_start=time(3)),
            patch(
                "homeassistant.components.daikin_onecta.coordinator.dt_util.DEFAULT_TIME_ZONE",
                amsterdam,
            ),
        ):
            assert coordinator._determine_update_interval() == timedelta(minutes=15)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_uses_repeated_dst_boundary_before_rollback(
        self, mock_now, coordinator
    ):
        """Use today's repeated boundary before daylight saving rollback."""
        amsterdam = ZoneInfo("Europe/Amsterdam")
        mock_now.return_value = datetime(2026, 10, 25, 2, 35, tzinfo=amsterdam)
        with (
            _patch_polling_schedule(high_start=time(2), low_start=time(2, 30)),
            patch(
                "homeassistant.components.daikin_onecta.coordinator.dt_util.DEFAULT_TIME_ZONE",
                amsterdam,
            ),
        ):
            assert coordinator._determine_update_interval() == timedelta(minutes=25)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    @patch("homeassistant.components.daikin_onecta.coordinator.random")
    def test_transition_period_randomization(self, mock_random, mock_now, coordinator):
        """During transition, randomize within the calculated poll intervals."""
        mock_now.return_value = datetime(2023, 1, 1, 22, 5, 0)
        mock_random.randint.return_value = 594

        with patch.object(coordinator, "_in_between", side_effect=[False, True]):
            expected = timedelta(seconds=594)
            result = coordinator._determine_update_interval()
            assert result == expected
            mock_random.randint.assert_called_once_with(594, 1782)

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

    async def test_api_error_uses_update_failed_with_http_status(self, coordinator):
        """Turn a Daikin HTTP error into a translatable polling failure."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(
            side_effect=OnectaApiError(
                500,
                "Internal Server Error",
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value.translation_key == "api_error"
        assert exc_info.value.translation_placeholders == {"status": "500"}

    async def test_post_write_cooldown_is_checked_under_cloud_lock(self, coordinator):
        """Keep cached data when a write completes while polling waits for the lock."""
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(return_value=None)

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator.api.get_cloud_device_details.assert_awaited_once_with(
            cooldown=timedelta(seconds=30)
        )
        assert coordinator.update_interval == timedelta(seconds=30)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_recent_write_skips_cloud_polling(self, mock_utcnow, coordinator):
        """Use the configured cooldown before polling after a recent write."""
        mock_utcnow.return_value = datetime(2023, 1, 1, 12, 0)
        coordinator.api.last_patch_call = mock_utcnow.return_value - timedelta(
            seconds=1
        )
        coordinator.api.get_cloud_device_details = AsyncMock()

        assert await coordinator._async_update_data_from_cloud() == {}
        assert coordinator.update_interval == timedelta(seconds=30)
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
            cooldown=timedelta(seconds=30)
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

    async def test_updated_cloud_device_replaces_cached_model(self, coordinator):
        """Replace the cached gateway model with cloud data."""
        existing_device = MagicMock()
        cloud_device = MagicMock(id="gateway")
        coordinator.data = {"gateway": existing_device}
        coordinator.api.last_patch_call = None
        coordinator.api.get_cloud_device_details = AsyncMock(
            return_value=[cloud_device]
        )

        await coordinator._async_update_data_from_cloud()

        existing_device.set_device_data.assert_called_once_with(cloud_device)
