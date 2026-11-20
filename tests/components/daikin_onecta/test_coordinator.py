"""Test the Daikin Onecta coordinator."""

import asyncio
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
    OnectaResponseError,
)
from daikin_onecta.models import Characteristic
from daikin_onecta.rate_limit import RateLimit
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
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
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .conftest import MockOnectaClient
from .platform_helpers import ALTHERMA_CLIMATE_ENTITY_ID, _async_fire_coordinator_update
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

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
    assert gateway.ha_device_id == entry.id


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
    await _async_setup_fixture(hass, config_entry, "altherma_firmwareupdate")
    device = next(iter(config_entry.runtime_data.data.values()))

    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.id), config_entry.entry_id
    )
    assert gateway_entry is not None
    point = device.device.management_points_by_type("userInterface")[0]
    point_entry = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{device.id}_{point.embedded_id}"), config_entry.entry_id
    )
    assert point_entry is not None
    assert point_entry.name == "User interface"
    assert point_entry.parent_device_id == gateway_entry.id


def test_device_update_ignores_management_point_metadata_changes() -> None:
    """Only metadata written to the gateway registry triggers an update."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_firmwareupdate")[0])
    replacement = deepcopy(device.device)
    point = replacement.management_points_by_type("indoorUnitHydro")[0]
    point.software_version = Characteristic(value="new-firmware")

    assert not device.set_device_data(replacement)


async def test_polling_child_firmware_change_does_not_update_gateway_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A child firmware change does not rewrite gateway-only registry metadata."""
    await _async_setup_fixture(hass, config_entry, "altherma_firmwareupdate")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    replacement = deepcopy(device.device)
    point = replacement.management_points_by_type("indoorUnitHydro")[0]
    point.software_version = Characteristic(value="new-firmware")
    coordinator._async_get_cloud_devices = AsyncMock(return_value=[replacement])
    registry = device_registry

    with patch.object(
        registry, "async_get_or_create", wraps=registry.async_get_or_create
    ) as async_get_or_create:
        await coordinator._async_update_data_from_cloud()

    async_get_or_create.assert_not_called()


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


async def test_rate_limited_poll_after_success_keeps_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep the last known state available when a poll is rate limited."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    caplog.clear()
    coordinator.client.get_gateway_devices = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
        )
    )
    assert coordinator.update_interval is not None
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    warnings = [
        record
        for record in caplog.records
        if record.name == "homeassistant.components.daikin_onecta.coordinator"
        and record.levelno >= logging.WARNING
    ]
    assert warnings == []
    assert coordinator.last_update_success
    coordinator.client.get_gateway_devices.assert_awaited_once_with()


async def test_poll_failure_is_logged_only_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log the transition to unavailable without repeating it each poll."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    coordinator = config_entry.runtime_data
    caplog.set_level(logging.INFO, logger=coordinator_module._LOGGER.name)
    coordinator.client.get_gateway_devices = AsyncMock(
        side_effect=OnectaConnectionError(
            EXPECTED_CONNECTION_ERROR,
            method="GET",
            path="/v1/gateway-devices",
        )
    )

    await _async_fire_coordinator_update(hass, coordinator, freezer)
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    unavailable_logs = [
        record
        for record in caplog.records
        if record.name == coordinator_module._LOGGER.name
        and "is unavailable" in record.message
    ]
    assert len(unavailable_logs) == 1


async def test_rate_limited_first_refresh_does_not_load_empty_cache(
    coordinator: OnectaDataUpdateCoordinator,
) -> None:
    """Do not treat the coordinator's initial success flag as cached data."""
    assert coordinator.last_update_success
    assert coordinator.data_or_none is None
    coordinator.client.get_gateway_devices = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
        )
    )

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data_from_cloud()

    assert err.value.translation_key == "rate_limit_exceeded"
    assert coordinator.data_or_none is None
    assert coordinator.client.get_gateway_devices.await_count == 1

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data_from_cloud()

    assert err.value.translation_key == "rate_limit_exceeded"
    assert coordinator.data_or_none is None
    assert coordinator.client.get_gateway_devices.await_count == 1


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

    def test_in_between_normal_range(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Time within a simple range not crossing midnight."""
        start = time(8, 0, 0)
        end = time(10, 0, 0)
        assert not coordinator._in_between(time(7, 0, 0), start, end)
        assert coordinator._in_between(time(8, 0, 0), start, end)
        assert coordinator._in_between(time(9, 0, 0), start, end)
        assert not coordinator._in_between(time(10, 0, 0), start, end)
        assert not coordinator._in_between(time(11, 0, 0), start, end)

    def test_in_between_overnight_range(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Time within a range that crosses midnight."""
        start = time(22, 0, 0)
        end = time(7, 0, 0)
        assert coordinator._in_between(time(6, 0, 0), start, end)
        assert not coordinator._in_between(time(7, 0, 0), start, end)
        assert not coordinator._in_between(time(12, 0, 0), start, end)
        assert coordinator._in_between(time(22, 0, 0), start, end)
        assert coordinator._in_between(time(23, 0, 0), start, end)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_high_scan_interval(
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """High scan interval should apply during high-frequency window."""
        mock_now.return_value = datetime(2023, 1, 1, 10, 0, 0)

        expected = timedelta(seconds=594)
        result = coordinator._determine_update_interval()
        assert result == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_low_scan_interval(
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Low scan interval should apply outside transition windows."""
        mock_now.return_value = datetime(2023, 1, 1, 23, 0, 0)

        with patch.object(coordinator, "_in_between", side_effect=[False, False]):
            expected = timedelta(seconds=1782)
            result = coordinator._determine_update_interval()
            assert result == expected

    def test_polling_intervals_use_default_daily_limit(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Use no more than 55% of the conservative default daily limit."""
        coordinator.client.rate_limit = RateLimit(day_limit=None)

        high_interval, low_interval = coordinator._polling_intervals()

        assert high_interval == timedelta(seconds=594)
        assert low_interval == timedelta(seconds=1782)
        assert ceil(15 * 3600 / 594) + ceil(9 * 3600 / 1782) == 110

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

    async def test_command_token_connection_error_returns_failure(
        self, coordinator: OnectaDataUpdateCoordinator, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Map OAuth transport failures to the platform's translated command error."""
        error = OAuth2TokenRequestConnectionError(domain=DOMAIN)
        coordinator.config_entry.async_start_reauth = MagicMock()
        caplog.set_level(logging.DEBUG, logger=coordinator_module._LOGGER.name)

        assert not await coordinator.async_execute_command(AsyncMock(side_effect=error))

        coordinator.config_entry.async_start_reauth.assert_not_called()
        assert coordinator.last_patch_call is None
        assert "OAuth2TokenRequestConnectionError" in caplog.text

    @pytest.mark.parametrize(
        ("status", "expected_reauth_calls"),
        [
            pytest.param(401, 1, id="unauthorized"),
            pytest.param(403, 0, id="forbidden"),
        ],
    )
    async def test_command_authentication_error_handles_status(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        status: int,
        expected_reauth_calls: int,
    ) -> None:
        """Only a 401 write failure starts reauthentication."""
        coordinator.config_entry.async_start_reauth = MagicMock()
        error = OnectaAuthenticationError(
            status=status,
            method="PATCH",
            path="/v1/management-points/point/characteristics/temperatureControl",
        )

        assert not await coordinator.async_execute_command(AsyncMock(side_effect=error))

        assert (
            coordinator.config_entry.async_start_reauth.call_count
            == expected_reauth_calls
        )
        assert coordinator.hass.config_entries.flow.async_progress() == []
        assert coordinator.last_patch_call is None

    def test_polling_intervals_use_reported_daily_limit(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Adapt the polling budget when Daikin reports a different limit."""
        coordinator.client.rate_limit = RateLimit(day_limit=400)

        assert coordinator._polling_intervals() == (
            timedelta(seconds=296),
            timedelta(seconds=888),
        )

    def test_polling_intervals_cap_a_1000_daily_limit(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Keep a 1000-call daily limit at the three-minute polling floor."""
        coordinator.client.rate_limit = RateLimit(day_limit=1000)

        assert coordinator._polling_intervals() == (
            timedelta(minutes=3),
            timedelta(minutes=9),
        )

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    async def test_cloud_response_updates_polling_interval_from_daily_limit(
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
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
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
        now: datetime,
        expected: timedelta,
    ) -> None:
        """Use at least the high-frequency interval near a window boundary."""
        mock_now.return_value = now
        assert coordinator._determine_update_interval() == expected

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.now")
    def test_scan_interval_uses_utc_delay_across_dst_start(
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
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
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
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
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
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
        self,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
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
    def test_transition_period_randomization(
        self,
        mock_random: MagicMock,
        mock_now: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """During transition, randomize within the calculated poll intervals."""
        mock_now.return_value = datetime(2023, 1, 1, 22, 5, 0)
        mock_random.randint.return_value = 594

        with patch.object(coordinator, "_in_between", side_effect=[False, True]):
            expected = timedelta(seconds=594)
            result = coordinator._determine_update_interval()
            assert result == expected
            mock_random.randint.assert_called_once_with(594, 1782)

    async def test_rate_limit_uses_update_failed_retry_after(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        freezer: FrozenDateTimeFactory,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """A Daikin rate limit should use the coordinator retry-after mechanism."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
            EXPECTED_CONNECTION_ERROR,
            method="GET",
            path="/v1/gateway-devices",
        )
        await _async_fire_coordinator_update(hass, coordinator, freezer)
        assert not coordinator.last_update_success
        state = hass.states.get(entity_id)
        assert state is not None and state.state == "unavailable"

        mock_onecta_client.get_gateway_devices.reset_mock()
        mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
            RateLimit(retry_after=EXPECTED_RATE_LIMIT_RETRY_AFTER),
            method="GET",
            path="/v1/gateway-devices",
        )
        await _async_fire_coordinator_update(hass, coordinator, freezer)

        assert not coordinator.last_update_success
        assert isinstance(coordinator.last_exception, UpdateFailed)
        assert coordinator.last_exception.retry_after == EXPECTED_RATE_LIMIT_RETRY_AFTER
        assert coordinator._polling_backoff_remaining() == timedelta(
            seconds=EXPECTED_RATE_LIMIT_RETRY_AFTER
        )

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    def test_polling_backoff_logs_start_and_end(
        self,
        mock_utcnow: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log once when the polling backoff starts and ends."""
        caplog.set_level(logging.INFO)
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        mock_utcnow.return_value = now

        coordinator._set_polling_backoff(60)
        mock_utcnow.return_value = now + timedelta(seconds=60)
        assert coordinator._polling_backoff_remaining() is None

        assert caplog.text.count("Daikin rate-limited cloud requests") == 1
        assert caplog.text.count("Daikin polling rate-limit backoff ended") == 1

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    def test_polling_backoff_remaining_rounds_up_fractional_seconds(
        self,
        mock_utcnow: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Round up remaining backoff so scheduled refreshes aren't early."""
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        mock_utcnow.return_value = now
        coordinator._polling_backoff_until = now + timedelta(milliseconds=500)

        assert coordinator._polling_backoff_remaining() == timedelta(seconds=1)

    async def test_manual_update_respects_get_retry_after(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        freezer: FrozenDateTimeFactory,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Manual entity refreshes keep cached state during a polling backoff."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
            RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
        )
        assert coordinator.update_interval is not None
        freezer.tick(coordinator.update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_onecta_client.get_gateway_devices.assert_awaited_once_with()
        mock_onecta_client.get_gateway_devices.reset_mock()
        mock_onecta_client.get_gateway_devices.side_effect = None
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None

        await async_update_entity(hass, entity_id)

        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert coordinator._polling_backoff_remaining() == timedelta(seconds=60)
        assert hass.states.get(entity_id) == state_before

    async def test_manual_update_rate_limit_keeps_cached_state_available(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
    ) -> None:
        """Keep the cached state available if a manual refresh is rate limited."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None
        coordinator.client.get_gateway_devices = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=60),
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        await async_update_entity(hass, entity_id)

        coordinator.client.get_gateway_devices.assert_awaited_once_with()
        assert coordinator.last_update_success
        assert coordinator._polling_backoff_until is not None
        assert hass.states.get(entity_id) == state_before

    async def test_manual_update_respects_write_polling_backoff(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Manual entity refreshes keep cached state during write backoff."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        command = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=60),
                method="PATCH",
                path="/v1/management-points/point/characteristics/power",
            )
        )
        assert not await coordinator.async_execute_command(lambda _client: command())
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None

        await async_update_entity(hass, entity_id)

        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert coordinator._polling_backoff_remaining() == timedelta(seconds=60)
        assert hass.states.get(entity_id) == state_before

    async def test_manual_updates_for_multiple_entities_are_debounced(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
    ) -> None:
        """One manual update for multiple climate entities makes one cloud call."""
        await _async_setup_fixture(hass, config_entry, "altherma")
        coordinator = config_entry.runtime_data
        coordinator.client.get_gateway_devices = AsyncMock(
            return_value=_load_gateway_devices("altherma")
        )
        entity_ids = [
            "climate.altherma_leaving_water_offset",
            "climate.altherma_leaving_water_temperature",
            ALTHERMA_CLIMATE_ENTITY_ID,
        ]

        await asyncio.gather(
            *(async_update_entity(hass, entity_id) for entity_id in entity_ids)
        )

        coordinator.client.get_gateway_devices.assert_awaited_once_with()

    async def test_scheduled_update_respects_write_polling_backoff(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        freezer: FrozenDateTimeFactory,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Scheduled polls keep using cached state during write backoff."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None
        command = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=3600),
                method="PATCH",
                path="/v1/management-points/point/characteristics/power",
            )
        )
        assert not await coordinator.async_execute_command(lambda _client: command())
        mock_onecta_client.get_gateway_devices.reset_mock()

        await _async_fire_coordinator_update(hass, coordinator, freezer)

        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert hass.states.get(entity_id) == state_before

    async def test_rate_limited_write_defers_polling(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        freezer: FrozenDateTimeFactory,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Defer manual entity refresh until a write's Retry-After expires."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None
        command = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=60),
                method="PATCH",
                path="/v1/gateway-devices/gateway/management-points/point/characteristics/power",
            )
        )

        assert not await coordinator.async_execute_command(lambda _client: command())
        mock_onecta_client.get_gateway_devices.reset_mock()
        mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices(
            "minimal_data"
        )

        await async_update_entity(hass, entity_id)
        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert hass.states.get(entity_id) == state_before
        command.assert_awaited_once()

        freezer.tick(timedelta(seconds=60))
        await _async_fire_coordinator_update(hass, coordinator, freezer)
        mock_onecta_client.get_gateway_devices.assert_awaited_once_with()

    async def test_manual_update_during_write_cooldown_keeps_failed_state(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        freezer: FrozenDateTimeFactory,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Keep entities unavailable if a manual update is deferred after a write."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
            EXPECTED_CONNECTION_ERROR,
            method="GET",
            path="/v1/gateway-devices",
        )
        await _async_fire_coordinator_update(hass, coordinator, freezer)
        assert not coordinator.last_update_success
        assert hass.states.get(entity_id).state == "unavailable"

        mock_onecta_client.get_gateway_devices.reset_mock()
        mock_onecta_client.get_gateway_devices.side_effect = None
        command = AsyncMock()
        assert await coordinator.async_execute_command(lambda _client: command())

        await async_update_entity(hass, entity_id)

        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert not coordinator.last_update_success
        assert hass.states.get(entity_id).state == "unavailable"

    async def test_poll_rechecks_backoff_after_acquiring_cloud_lock(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        mock_onecta_client: MockOnectaClient,
    ) -> None:
        """Keep entity state if a refresh waits on a rate-limited command."""
        await _async_setup_fixture(hass, config_entry, "minimal_data")
        coordinator = config_entry.runtime_data
        entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
        state_before = hass.states.get(entity_id)
        assert state_before is not None
        mock_onecta_client.get_gateway_devices.reset_mock()
        command_started = asyncio.Event()
        finish_command = asyncio.Event()

        async def rate_limited_command(_client: object) -> None:
            command_started.set()
            await finish_command.wait()
            raise OnectaRateLimitError(
                RateLimit(retry_after=60),
                method="PATCH",
                path="/v1/management-points/point/characteristics/power",
            )

        command_task = hass.async_create_task(
            coordinator.async_execute_command(rate_limited_command)
        )
        await command_started.wait()
        poll_task = hass.async_create_task(async_update_entity(hass, entity_id))
        await asyncio.sleep(0)
        finish_command.set()
        assert not await command_task

        await poll_task
        mock_onecta_client.get_gateway_devices.assert_not_awaited()
        assert coordinator.last_update_success
        assert hass.states.get(entity_id) == state_before

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_successful_write_clears_polling_backoff(
        self,
        mock_utcnow: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Allow commands through during polling backoff and clear it on success."""
        now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        mock_utcnow.return_value = now
        rate_limited_command = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=60),
                method="PATCH",
                path="/v1/management-points/point/characteristics/power",
            )
        )
        assert not await coordinator.async_execute_command(
            lambda _client: rate_limited_command()
        )
        command = AsyncMock()

        assert await coordinator.async_execute_command(lambda _client: command())

        command.assert_awaited_once()
        assert coordinator._polling_backoff_until is None

    async def test_successful_write_reschedules_poll_after_cooldown(
        self,
        hass: HomeAssistant,
        freezer: FrozenDateTimeFactory,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Poll 30 seconds after a successful write clears the backoff."""
        coordinator.update_interval = timedelta(minutes=5)
        coordinator.client.get_gateway_devices = AsyncMock(return_value=[])

        rate_limited_command = AsyncMock(
            side_effect=OnectaRateLimitError(
                RateLimit(retry_after=300),
                method="PATCH",
                path="/v1/management-points/point/characteristics/power",
            )
        )
        assert not await coordinator.async_execute_command(
            lambda _client: rate_limited_command()
        )
        command = AsyncMock()
        assert await coordinator.async_execute_command(lambda _client: command())

        freezer.tick(timedelta(seconds=29))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        coordinator.client.get_gateway_devices.assert_not_awaited()

        freezer.tick(timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        coordinator.client.get_gateway_devices.assert_awaited_once_with()

    async def test_api_error_uses_update_failed_with_http_status(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
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

    async def test_response_error_uses_invalid_response_message(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Explain malformed successful API responses without an HTTP error status."""
        coordinator._last_patch_call = None
        response_error = OnectaResponseError(
            200,
            "Invalid JSON",
            method="GET",
            path="/v1/gateway-devices",
        )
        coordinator._async_get_cloud_devices = AsyncMock(side_effect=response_error)

        with pytest.raises(UpdateFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value.translation_key == "invalid_response"
        assert exc_info.value.__cause__ is response_error

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

    async def test_token_refresh_reauth_error_requires_authentication(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Translate OAuth refresh rejection into an authentication failure."""
        coordinator._last_patch_call = None
        token_error = OAuth2TokenRequestReauthError(
            domain=DOMAIN,
            request_info=MagicMock(),
            status=401,
            message="invalid_grant",
        )
        coordinator._async_get_cloud_devices = AsyncMock(side_effect=token_error)

        with pytest.raises(ConfigEntryAuthFailed) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value.translation_key == "authentication_failed"
        assert exc_info.value.__cause__ is token_error

    async def test_transient_token_refresh_error_is_retried(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Preserve transient OAuth token errors so the coordinator retries."""
        coordinator._last_patch_call = None
        token_error = OAuth2TokenRequestError(
            domain=DOMAIN,
            request_info=MagicMock(),
            status=500,
            message="server error",
        )
        coordinator._async_get_cloud_devices = AsyncMock(side_effect=token_error)

        with pytest.raises(OAuth2TokenRequestError) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert exc_info.value is token_error

    async def test_post_write_cooldown_is_checked_under_cloud_lock(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Keep cached data when a write completes while polling waits for the lock."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=None)

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator._async_get_cloud_devices.assert_awaited_once_with()
        assert coordinator.update_interval == timedelta(seconds=30)

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_recent_write_skips_cloud_polling(
        self,
        mock_utcnow: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Use the configured cooldown before polling after a recent write."""
        mock_utcnow.return_value = datetime(2023, 1, 1, 12, 0)
        coordinator._last_patch_call = mock_utcnow.return_value - timedelta(seconds=1)
        coordinator._async_get_cloud_devices = AsyncMock()

        assert await coordinator._async_update_data_from_cloud() == {}
        assert coordinator.update_interval == timedelta(seconds=30)
        coordinator._async_get_cloud_devices.assert_not_awaited()

    @patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
    async def test_post_write_cooldown_uses_utc_across_dst_rollback(
        self,
        mock_utcnow: MagicMock,
        coordinator: OnectaDataUpdateCoordinator,
    ) -> None:
        """Do not extend cooldown when local time moves backward."""
        # In Amsterdam, local time moves from 02:59 CEST back to 02:01 CET here.
        coordinator._last_patch_call = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)
        mock_utcnow.return_value = datetime(2026, 10, 25, 1, 1, tzinfo=UTC)
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[])

        assert await coordinator._async_update_data_from_cloud() == {}
        coordinator._async_get_cloud_devices.assert_awaited_once_with()

    async def test_connection_error_uses_update_failed(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """A connection error should mark the coordinator update as failed."""
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(
            side_effect=OnectaConnectionError(
                EXPECTED_CONNECTION_ERROR,
                method="GET",
                path="/v1/gateway-devices",
            )
        )

        with pytest.raises(UpdateFailedUnreachable) as exc_info:
            await coordinator._async_update_data_from_cloud()

        assert isinstance(exc_info.value.__cause__, OnectaConnectionError)
        assert exc_info.value.translation_key == "connection_failed"

    async def test_cooldown_fetch_failure_restores_regular_interval(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
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

    async def test_missing_cloud_device_is_marked_unavailable(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Mark cached gateways unavailable when the cloud no longer returns them."""
        missing_device = MagicMock()
        missing_device.device = MagicMock(id="missing", management_points=[])
        coordinator.data = {"missing": missing_device}
        coordinator._last_patch_call = None
        coordinator._async_get_cloud_devices = AsyncMock(return_value=[])

        await coordinator._async_update_data_from_cloud()

        missing_device.mark_unavailable.assert_called_once_with()
        coordinator.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_new_cloud_gateway_does_not_reload_entry(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Platform listeners handle newly reported gateways without a reload."""
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

        coordinator.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_new_management_point_does_not_reload_entry(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
        """Platform listeners handle new points without a config-entry reload."""
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

        coordinator.hass.config_entries.async_schedule_reload.assert_not_called()

    async def test_cloud_state_update_does_not_reload_entry(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
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

    async def test_updated_cloud_device_replaces_cached_model(
        self, coordinator: OnectaDataUpdateCoordinator
    ) -> None:
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
