"""Test the Daikin Onecta coordinator."""

from copy import deepcopy
from datetime import UTC, datetime, time, timedelta
import logging
from math import ceil
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from daikin_onecta import (
    OnectaApiError,
    OnectaAuthenticationError,
    OnectaConnectionError,
    OnectaRateLimitError,
)
from daikin_onecta.models import Characteristic
from daikin_onecta.rate_limit import RateLimit
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.daikin_onecta import (
    PLATFORMS,
    coordinator as coordinator_module,
)
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

from tests.common import MockConfigEntry, async_fire_time_changed

EXPECTED_RATE_LIMIT_RETRY_AFTER = 3060
EXPECTED_CONNECTION_ERROR = "network unavailable"


def test_device_update_detects_registry_metadata_changes() -> None:
    """Use the replacement cloud model's name in device-registry metadata."""
    device = DaikinOnectaDevice(
        SimpleNamespace(
            id="gateway",
            display_name="Old name",
            available=True,
            mac_address=None,
            device_model=None,
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )

    assert device.set_device_data(
        SimpleNamespace(
            id="gateway",
            display_name="New name",
            available=True,
            mac_address=None,
            device_model=None,
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )

    assert device.name == "New name"


def test_device_update_ignores_unchanged_registry_metadata() -> None:
    """Avoid rewriting a device registry entry for unchanged cloud metadata."""
    device = DaikinOnectaDevice(
        SimpleNamespace(
            id="gateway",
            display_name="Name",
            available=True,
            mac_address=None,
            device_model="Model",
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )

    assert not device.set_device_data(
        SimpleNamespace(
            id="gateway",
            display_name="Name",
            available=True,
            mac_address=None,
            device_model="Model",
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )


async def test_device_registry_refreshes_without_climate_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Refresh a gateway registry entry even when it has no climate entity."""
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    gateway = DaikinOnectaDevice(
        SimpleNamespace(
            id="gateway",
            display_name="Old name",
            available=True,
            mac_address=None,
            device_model="Old model",
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )
    coordinator._async_register_device(gateway)
    gateway.set_device_data(
        SimpleNamespace(
            id="gateway",
            display_name="New name",
            available=True,
            mac_address=None,
            device_model="New model",
            gateway_embedded_id=None,
            gateway_management_point=None,
        )
    )
    coordinator._async_register_device(gateway)

    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "gateway"), config_entry.entry_id
    )
    assert entry is not None
    assert entry.name == "New name"
    assert entry.model_id == "New model"


@pytest.mark.parametrize(
    ("mac_address", "expected_connections"),
    [
        ("02:00:00:00:00:01", {(dr.CONNECTION_NETWORK_MAC, "02:00:00:00:00:01")}),
        (None, set()),
    ],
)
async def test_device_registry_updates_changed_mac_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    mac_address: str | None,
    expected_connections: set[tuple[str, str]],
) -> None:
    """Detect MAC-only changes and replace, rather than retain, stale connections."""
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    gateway = DaikinOnectaDevice(_load_gateway_devices("ururu")[0])
    coordinator._async_register_device(gateway)
    replacement = deepcopy(gateway.device)
    replacement.gateway_management_point.characteristics["macAddress"] = Characteristic(
        value=mac_address
    )

    assert gateway.set_device_data(replacement)
    coordinator._async_register_device(gateway)

    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway.id), config_entry.entry_id
    )
    assert entry is not None
    assert entry.connections == expected_connections
    assert not gateway.set_device_data(deepcopy(replacement))


async def test_management_point_hardware_is_registered_as_subdevice(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Register physical management points beneath their cloud gateway."""
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_firmwareupdate")[0])

    coordinator._async_register_device(device)

    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.id), config_entry.entry_id
    )
    assert gateway_entry is not None
    point = device.device.management_points_by_type("indoorUnitHydro")[0]
    point_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.id}_{point.embedded_id}"), config_entry.entry_id
    )
    assert point_entry is not None
    assert point_entry.name == f"{device.name} Indoor hydro unit"
    assert point_entry.model == point.model
    assert point_entry.sw_version == point.version
    assert point_entry.via_device_id == gateway_entry.id


def test_device_update_detects_management_point_metadata_changes() -> None:
    """Refresh registry metadata when physical management-point data changes."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_firmwareupdate")[0])
    replacement = deepcopy(device.device)
    point = replacement.management_points_by_type("indoorUnitHydro")[0]
    point.software_version = Characteristic(value="new-firmware")

    assert device.set_device_data(replacement)


async def test_poll_refreshes_changed_metadata_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Refresh renamed gateways and firmware only after changed cloud metadata."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    replacement = deepcopy(device.device)
    point = replacement.management_point("climateControl")
    assert point is not None
    point.name = Characteristic(value="Renamed Daikin")
    gateway = replacement.gateway_management_point
    assert gateway is not None
    gateway.firmware_version = Characteristic(value="new-firmware")

    with (
        patch.object(
            coordinator,
            "_async_register_device",
            wraps=coordinator._async_register_device,
        ) as update_registry,
        patch.object(
            coordinator, "_async_get_cloud_devices", return_value=[replacement]
        ),
    ):
        assert coordinator.update_interval is not None
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        update_registry.assert_called_once_with(device)
        coordinator.async_update_listeners()
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        update_registry.assert_called_once_with(device)

    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.id), config_entry.entry_id
    )
    assert entry is not None
    assert entry.name == "Renamed Daikin"
    assert entry.sw_version == "new-firmware"


async def test_poll_failure_logged_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Leave failure/recovery logging to the coordinator, without duplicate warnings."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    caplog.clear()
    with patch.object(
        coordinator,
        "_async_get_cloud_devices",
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
        ),
    ):
        assert coordinator.update_interval is not None
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    failures = [
        record
        for record in caplog.records
        if record.name == "homeassistant.components.daikin_onecta.coordinator"
        and record.levelno >= logging.WARNING
    ]
    assert len(failures) == 1
    assert "Daikin API rate limit exceeded" in failures[0].getMessage()


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
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="daikin_onecta",
        unique_id="12345",
        options={},
    )


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> OnectaDataUpdateCoordinator:
    """Return a coordinator."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_schedule_reload = MagicMock()
    coordinator = OnectaDataUpdateCoordinator(hass, mock_config_entry, MagicMock())
    coordinator._async_register_device = MagicMock()
    return coordinator


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
        coordinator.client.rate_limit = RateLimit(day_limit=None)

        high_interval, low_interval = coordinator._polling_intervals()

        assert high_interval == timedelta(seconds=594)
        assert low_interval == timedelta(seconds=1782)
        assert ceil(15 * 3600 / 594) + ceil(9 * 3600 / 1782) == 110

    async def test_command_token_rejection_starts_reauthentication(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Start reauthentication when token renewal rejects a command."""
        error = OAuth2TokenRequestReauthError(
            domain=DOMAIN,
            request_info=MagicMock(),
            status=401,
            message="invalid_grant",
        )
        command = AsyncMock(side_effect=error)
        coordinator.config_entry.async_start_reauth = MagicMock()

        assert not await coordinator.async_execute_command(command)

        coordinator.config_entry.async_start_reauth.assert_called_once_with(
            coordinator.hass
        )
        assert coordinator.last_patch_call is None

    async def test_transient_command_token_failure_returns_failure(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Map a transient token renewal failure to a failed command."""
        error = OAuth2TokenRequestError(
            domain=DOMAIN,
            request_info=MagicMock(),
            status=500,
            message="server error",
        )

        assert not await coordinator.async_execute_command(AsyncMock(side_effect=error))
        assert coordinator.last_patch_call is None

    def test_polling_intervals_use_reported_daily_limit(self, coordinator):
        """Adapt the polling budget when Daikin reports a different limit."""
        coordinator.client.rate_limit = RateLimit(day_limit=400)

        assert coordinator._polling_intervals() == (
            timedelta(seconds=296),
            timedelta(seconds=888),
        )

    def test_polling_intervals_cap_a_1000_daily_limit(self, coordinator):
        """Keep a 1000-call daily limit at the three-minute polling floor."""
        coordinator.client.rate_limit = RateLimit(day_limit=1000)

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
        coordinator._last_patch_call = None
        coordinator.client.rate_limit = RateLimit(day_limit=400)
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[])

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
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """A Daikin rate limit should use the coordinator retry-after mechanism."""
        daikin_api = coordinator
        daikin_api._last_patch_call = None
        daikin_api._async_get_cloud_devices = AsyncMock(
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

    async def test_api_error_uses_update_failed_with_http_status(self, coordinator):
        """Turn a Daikin HTTP error into a translatable polling failure."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(
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

    @pytest.mark.parametrize("status", [401, 403])
    async def test_unauthorized_api_error_requires_authentication(
        self, coordinator: OnectaDataUpdateCoordinator, status: int
    ) -> None:
        """A rejected cloud token must not become a polling retry."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(
            side_effect=OnectaAuthenticationError(
                status=status,
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        with pytest.raises(ConfigEntryAuthFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value.translation_key == "authentication_failed"

    async def test_token_refresh_reauth_error_propagates(self, coordinator):
        """Preserve OAuth refresh failures for Home Assistant reauthentication."""
        coordinator._last_patch_call = None
        token_error = OAuth2TokenRequestReauthError(
            domain=DOMAIN,
            request_info=MagicMock(),
            status=401,
            message="invalid_grant",
        )
        coordinator._async_get_cloud_devices = AsyncMock(side_effect=token_error)

        with pytest.raises(OAuth2TokenRequestReauthError) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value is token_error

    async def test_post_write_cooldown_is_checked_under_cloud_lock(self, coordinator):
        """Keep cached data when a write completes while polling waits for the lock."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=None)

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator._async_get_cloud_devices.assert_awaited_once_with(
            cooldown=timedelta(seconds=30)
        )
        assert coordinator.update_interval == timedelta(seconds=30)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_recent_write_skips_cloud_polling(self, mock_utcnow, coordinator):
        """Use the configured cooldown before polling after a recent write."""
        mock_utcnow.return_value = datetime(2023, 1, 1, 12, 0)
        coordinator._last_patch_call = mock_utcnow.return_value - timedelta(seconds=1)
        coordinator._async_get_cloud_devices = AsyncMock()

        assert await coordinator._async_update_data_from_cloud() == {}
        assert coordinator.update_interval == timedelta(seconds=30)
        coordinator._async_get_cloud_devices.assert_not_awaited()

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_post_write_cooldown_uses_utc_across_dst_rollback(
        self, mock_utcnow, coordinator
    ):
        """Do not extend cooldown when local time moves backward."""
        # In Amsterdam, local time moves from 02:59 CEST back to 02:01 CET here.
        coordinator._last_patch_call = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)
        mock_utcnow.return_value = datetime(2026, 10, 25, 1, 1, tzinfo=UTC)
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[])

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator._async_get_cloud_devices.assert_awaited_once_with(
            cooldown=timedelta(seconds=30)
        )

    async def test_connection_error_uses_update_failed(self, coordinator):
        """A connection error should mark the coordinator update as failed."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(
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

    async def test_cooldown_fetch_failure_restores_regular_interval(self, coordinator):
        """Do not retain the cooldown polling interval after a failed fetch."""
        coordinator._last_patch_call = None
        coordinator.update_interval = timedelta(seconds=30)
        expected_interval = coordinator._determine_update_interval()
        coordinator._async_get_cloud_devices = AsyncMock(
            side_effect=OnectaConnectionError(
                EXPECTED_CONNECTION_ERROR,
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data_from_cloud()

        assert coordinator.update_interval == expected_interval

    async def test_missing_cloud_device_is_marked_unavailable(self, coordinator):
        """Mark cached gateways unavailable when the cloud no longer returns them."""
        missing_device = MagicMock()
        missing_device.device = MagicMock(id="missing", management_points=[])
        coordinator.data = {"missing": missing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[])

        await coordinator._async_update_data_from_cloud()

        missing_device.mark_unavailable.assert_called_once_with()
        coordinator.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_new_cloud_gateway_schedules_reload(self, coordinator):
        """Reload platforms when ONECTA reports a newly added gateway."""
        existing_device = MagicMock()
        existing_device.device = MagicMock(id="existing", management_points=[])
        existing_device.set_device_data.return_value = False
        new_device = MagicMock(
            id="new",
            display_name="New device",
            available=True,
            device_model="BRP069",
            gateway_embedded_id=None,
            mac_address=None,
            management_points=[],
        )
        coordinator.data = {"existing": existing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(
            return_value=[existing_device.device, new_device]
        )

        await coordinator._async_update_data_from_cloud()

        coordinator.hass.config_entries.async_schedule_reload.assert_called_once_with(
            coordinator.config_entry.entry_id
        )

    async def test_new_management_point_schedules_reload(self, coordinator):
        """Reload platforms when ONECTA adds a management point."""
        existing_device = MagicMock()
        existing_device.device = MagicMock(
            id="gateway",
            management_points=[
                MagicMock(
                    embedded_id="climate",
                    management_point_type="climateControl",
                )
            ],
        )
        existing_device.set_device_data.return_value = False
        updated_device = MagicMock(
            id="gateway",
            management_points=[
                MagicMock(
                    embedded_id="climate",
                    management_point_type="climateControl",
                ),
                MagicMock(
                    embedded_id="hot_water",
                    management_point_type="domesticHotWaterTank",
                ),
            ],
        )
        coordinator.data = {"gateway": existing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[updated_device])

        await coordinator._async_update_data_from_cloud()

        coordinator.hass.config_entries.async_schedule_reload.assert_called_once_with(
            coordinator.config_entry.entry_id
        )

    async def test_unchanged_cloud_topology_does_not_schedule_reload(self, coordinator):
        """Do not reload platforms for ordinary state updates."""
        existing_device = MagicMock()
        cloud_device = MagicMock(id="gateway", management_points=[])
        existing_device.device = cloud_device
        existing_device.set_device_data.return_value = False
        coordinator.data = {"gateway": existing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[cloud_device])

        await coordinator._async_update_data_from_cloud()

        coordinator.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_updated_cloud_device_replaces_cached_model(self, coordinator):
        """Replace the cached gateway model with cloud data."""
        existing_device = MagicMock()
        existing_device.set_device_data.return_value = False
        cloud_device = MagicMock(id="gateway")
        coordinator.data = {"gateway": existing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[cloud_device])

        await coordinator._async_update_data_from_cloud()

        existing_device.set_device_data.assert_called_once_with(cloud_device)
        coordinator._async_register_device.assert_not_called()

    async def test_changed_gateway_metadata_refreshes_device_registry(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Refresh the registry only when a cloud replacement changes metadata."""
        existing_device = MagicMock()
        existing_device.set_device_data.return_value = True
        cloud_device = MagicMock(id="gateway")
        coordinator.data = {"gateway": existing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[cloud_device])

        await coordinator._async_update_data_from_cloud()

        coordinator._async_register_device.assert_called_once_with(existing_device)


async def test_device_registered_before_platform_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Register gateways upfront even when they have no supported climate target."""
    gateway = _load_gateway_devices("mc80z")[0]

    async def forward_platforms(
        entry: MockConfigEntry, platforms: list[Platform]
    ) -> None:
        assert (
            device_registry.async_get_device_by_identifier(
                (DOMAIN, gateway.id), entry.entry_id
            )
            is not None
        )

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new=AsyncMock(side_effect=forward_platforms),
    ) as forward:
        await _async_setup_fixture(hass, config_entry, "mc80z")

    forward.assert_awaited_once_with(config_entry, PLATFORMS)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, gateway.id), config_entry.entry_id
        )
        is not None
    )
