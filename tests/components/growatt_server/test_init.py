"""Tests for the Growatt Server integration."""

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import timedelta
import json
import threading
from typing import Any
from unittest.mock import MagicMock, Mock

from freezegun.api import FrozenDateTimeFactory
import growattServer
from growattServer import GrowattV1ApiErrorCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_PLANT_ID,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
)
from homeassistant.components.growatt_server.coordinator import (
    LOGIN_COOLDOWN,
    RELOGIN_INTERVAL,
    GrowattClassicSession,
    GrowattLoginRateLimited,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration

# Growatt redirects requests on an expired session to an HTML login page.
SESSION_EXPIRED = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
TLX_OUTPUT_POWER = "sensor.tlx123456_output_power"
WEB_PAGE_ISSUE_ID = "unexpected_web_page_{entry_id}"


def tlx_detail(pac: int) -> dict[str, Any]:
    """Return a TLX detail response with the given output power."""
    return {"data": {"deviceSn": "TLX123456", "pac": pac}}


@pytest.mark.usefixtures("init_integration")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_device_info(
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device registry integration."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "MIN123456"), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            growattServer.GrowattV1ApiError(
                message="API Error",
                error_code=GrowattV1ApiErrorCode.WRONG_DOMAIN,
                error_msg="Invalid JSON",
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            json.decoder.JSONDecodeError("Invalid JSON", "", 0),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            growattServer.GrowattV1ApiError(
                message="Rate limited",
                error_code=GrowattV1ApiErrorCode.RATE_LIMITED,
                error_msg="Access frequency limit",
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_error_on_api_failure(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup error on API failures during device list."""
    mock_growatt_v1_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles update failures gracefully."""
    # Integration should be loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Cause coordinator update to fail
    mock_growatt_v1_api.min_detail.side_effect = growattServer.GrowattV1ApiError(
        message="Rate limited",
        error_code=growattServer.GrowattV1ApiErrorCode.RATE_LIMITED,
        error_msg="Too many requests",
    )

    # Trigger coordinator refresh
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Integration should remain loaded despite coordinator error
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_json_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles JSONDecodeError gracefully."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_growatt_v1_api.min_detail.side_effect = json.decoder.JSONDecodeError(
        "Invalid JSON", "", 0
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("switch.min123456_charge_from_grid").state == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_total_non_auth_api_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test total coordinator handles non-auth V1 API errors as UpdateFailed."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    error = growattServer.GrowattV1ApiError(
        message="Rate limited",
        error_code=growattServer.GrowattV1ApiErrorCode.RATE_LIMITED,
        error_msg="Too many requests",
    )
    mock_growatt_v1_api.plant_energy_overview.side_effect = error

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Should stay loaded (UpdateFailed is transient), no reauth flow started
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert not any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_setup_auth_failed_on_permission_denied(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error 10011 from device_list triggers reauth during setup."""
    error = growattServer.GrowattV1ApiError(
        message="Permission denied",
        error_code=growattServer.GrowattV1ApiErrorCode.NO_PRIVILEGE,
        error_msg="dummy error",
    )
    mock_growatt_v1_api.device_list.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    # Verify a reauth flow was started
    flows = hass.config_entries.flow.async_progress()
    assert any(
        flow["context"]["source"] == "reauth"
        and flow["context"]["entry_id"] == mock_config_entry.entry_id
        for flow in flows
    )


async def test_coordinator_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that error 10011 (no privilege) from coordinator update triggers reauth."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    error = growattServer.GrowattV1ApiError(
        message="Permission denied",
        error_code=growattServer.GrowattV1ApiErrorCode.NO_PRIVILEGE,
        error_msg="dummy error",
    )
    mock_growatt_v1_api.min_detail.side_effect = error

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify a reauth flow was started
    flows = hass.config_entries.flow.async_progress()
    assert any(
        flow["context"]["source"] == "reauth"
        and flow["context"]["entry_id"] == mock_config_entry.entry_id
        for flow in flows
    )
    assert (
        hass.states.get("switch.min123456_charge_from_grid").state == STATE_UNAVAILABLE
    )


async def test_classic_api_coordinator_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test invalid classic API credentials trigger reauth on update."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    mock_growatt_classic_api.plant_info.return_value = {
        "deviceList": [],
        "totalEnergy": 1250.0,
        "todayEnergy": 12.5,
        "invTodayPpv": 2500,
        "plantMoneyText": "123.45/USD",
    }
    mock_growatt_classic_api.tlx_detail.return_value = {
        "data": {"deviceSn": "TLX123456"}
    }

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # The session expires and the credentials are no longer valid on re-login
    mock_growatt_classic_api.tlx_detail.side_effect = SESSION_EXPIRED
    mock_growatt_classic_api.login.return_value = {
        "success": False,
        "msg": LOGIN_INVALID_AUTH_CODE,
    }

    freezer.tick(RELOGIN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert any(
        flow["context"]["source"] == "reauth"
        and flow["context"]["entry_id"] == mock_config_entry_classic.entry_id
        for flow in flows
    )
    assert hass.states.get(TLX_OUTPUT_POWER).state == STATE_UNAVAILABLE


async def test_classic_api_polls_reuse_session(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test consecutive Classic API polls reuse the setup login."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    for pac in (1000, 1100, 1200):
        mock_growatt_classic_api.tlx_detail.return_value = tlx_detail(pac)
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # One login at setup, shared by the total and device coordinators.
    mock_growatt_classic_api.login.assert_called_once()
    assert mock_growatt_classic_api.tlx_detail.call_count == 4
    assert hass.states.get(TLX_OUTPUT_POWER).state == "1200"


async def test_classic_api_expired_session_logs_in_again(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an expired Classic API session triggers one re-login and a retry."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.reset_mock()
    mock_growatt_classic_api.tlx_detail.reset_mock()

    mock_growatt_classic_api.tlx_detail.side_effect = [
        SESSION_EXPIRED,
        tlx_detail(1500),
    ]

    freezer.tick(RELOGIN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_growatt_classic_api.login.assert_called_once_with("test_user", "test_password")
    assert mock_growatt_classic_api.tlx_detail.call_count == 2
    coordinator = mock_config_entry_classic.runtime_data.devices["TLX123456"]
    assert coordinator.last_update_success
    assert hass.states.get(TLX_OUTPUT_POWER).state == "1500"


@pytest.mark.parametrize(
    ("login_response", "tlx_detail_side_effect", "translation_key"),
    [
        pytest.param(
            {"success": False, "msg": "Server maintenance"},
            SESSION_EXPIRED,
            "login_failed",
            id="login_fails",
        ),
        pytest.param(
            {"success": True, "user": {"id": 12345}},
            [SESSION_EXPIRED, SESSION_EXPIRED],
            "unexpected_web_page",
            id="retry_fails",
        ),
    ],
)
async def test_classic_api_expired_session_relogin_failure(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    login_response: dict,
    tlx_detail_side_effect: Exception | list[Exception],
    translation_key: str,
) -> None:
    """Test a failed re-login or retry after session expiry fails the update."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.reset_mock()

    mock_growatt_classic_api.tlx_detail.side_effect = tlx_detail_side_effect
    mock_growatt_classic_api.login.return_value = login_response

    freezer.tick(RELOGIN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_growatt_classic_api.login.assert_called_once()
    coordinator = mock_config_entry_classic.runtime_data.devices["TLX123456"]
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == translation_key
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()
    assert hass.states.get(TLX_OUTPUT_POWER).state == STATE_UNAVAILABLE


async def test_classic_api_rate_limited_relogin_cooldown(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a 507 on re-login stops further logins until the cooldown passes."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    plant_info = mock_growatt_classic_api.plant_info.return_value

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.reset_mock()

    mock_growatt_classic_api.plant_info.side_effect = SESSION_EXPIRED
    mock_growatt_classic_api.tlx_detail.side_effect = SESSION_EXPIRED
    mock_growatt_classic_api.login.return_value = {"success": False, "msg": "507"}

    freezer.tick(RELOGIN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for _ in range(2):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Only the first coordinator to find the expired session tries to log in.
    mock_growatt_classic_api.login.assert_called_once()
    coordinator = mock_config_entry_classic.runtime_data.devices["TLX123456"]
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "login_rate_limited"
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    assert hass.states.get(TLX_OUTPUT_POWER).state == STATE_UNAVAILABLE

    mock_growatt_classic_api.plant_info.side_effect = [SESSION_EXPIRED, plant_info]
    mock_growatt_classic_api.tlx_detail.side_effect = None
    mock_growatt_classic_api.tlx_detail.return_value = tlx_detail(1700)
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 12345},
    }
    freezer.tick(LOGIN_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_growatt_classic_api.login.call_count == 2
    assert coordinator.last_update_success
    assert hass.states.get(TLX_OUTPUT_POWER).state == "1700"


async def test_classic_session_concurrent_renew_logs_in_once(
    hass: HomeAssistant,
) -> None:
    """Test a renew that waits on another coordinator's login does not log in."""
    entered = threading.Event()
    release = threading.Event()

    def blocking_login(username: str, password: str) -> dict[str, Any]:
        entered.set()
        release.wait(5)
        return {"success": True}

    api = Mock()
    api.login.side_effect = blocking_login
    session = GrowattClassicSession(hass, api, "test_user", "test_password")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(session.renew, 0)
        assert entered.wait(5)
        second = pool.submit(session.renew, 0)
        # The second renew must be blocked on the lock while the first logs in.
        done, _ = wait([second], timeout=0.2)
        assert not done
        release.set()
        assert first.result(5) == {"success": True}
        assert second.result(5) is None

    api.login.assert_called_once_with("test_user", "test_password")
    assert session.generation == 1


async def test_classic_api_web_page_with_working_login_bounds_logins(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test data requests that keep returning HTML do not cost a login per poll."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    plant_info = mock_growatt_classic_api.plant_info.return_value

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.reset_mock()

    # Login keeps working, but data requests get a web page, as with a
    # pending terms prompt.
    mock_growatt_classic_api.plant_info.side_effect = SESSION_EXPIRED
    mock_growatt_classic_api.tlx_detail.side_effect = SESSION_EXPIRED

    # 4 hours of 5-minute polls
    for _ in range(48):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    # At most one login per RELOGIN_INTERVAL, shared by both coordinators.
    assert mock_growatt_classic_api.login.call_count == 8
    coordinator = mock_config_entry_classic.runtime_data.devices["TLX123456"]
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "unexpected_web_page"
    issue_id = WEB_PAGE_ISSUE_ID.format(entry_id=mock_config_entry_classic.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    assert hass.states.get(TLX_OUTPUT_POWER).state == STATE_UNAVAILABLE

    mock_growatt_classic_api.plant_info.side_effect = None
    mock_growatt_classic_api.plant_info.return_value = plant_info
    mock_growatt_classic_api.tlx_detail.side_effect = None
    mock_growatt_classic_api.tlx_detail.return_value = tlx_detail(1800)
    freezer.tick(RELOGIN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert hass.states.get(TLX_OUTPUT_POWER).state == "1800"


async def test_classic_api_web_page_at_setup_raises_issue(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a web page right after the setup login raises the repair issue."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    mock_growatt_classic_api.plant_info.side_effect = SESSION_EXPIRED
    mock_growatt_classic_api.tlx_detail.side_effect = SESSION_EXPIRED

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_RETRY
    mock_growatt_classic_api.login.assert_called_once()

    # Setup retries wait out RELOGIN_INTERVAL, so 4 hours cost 8 more logins.
    for _ in range(240):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_growatt_classic_api.login.call_count == 9
    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_RETRY
    issue = issue_registry.async_get_issue(
        DOMAIN, WEB_PAGE_ISSUE_ID.format(entry_id=mock_config_entry_classic.entry_id)
    )
    assert issue
    assert issue.config_entry_id == mock_config_entry_classic.entry_id


async def test_classic_api_early_expiry_waits_for_relogin_interval(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a session that dies soon after a login waits before logging in."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.reset_mock()

    mock_growatt_classic_api.tlx_detail.side_effect = SESSION_EXPIRED
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_growatt_classic_api.login.assert_not_called()
    coordinator = mock_config_entry_classic.runtime_data.devices["TLX123456"]
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "relogin_throttled"

    mock_growatt_classic_api.tlx_detail.side_effect = [
        SESSION_EXPIRED,
        tlx_detail(1900),
    ]
    freezer.tick(RELOGIN_INTERVAL - timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_growatt_classic_api.login.assert_called_once()
    assert hass.states.get(TLX_OUTPUT_POWER).state == "1900"


async def test_classic_api_setup_retry_reuses_session(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup retries after a failed first refresh do not log in again."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    plant_info = mock_growatt_classic_api.plant_info.return_value
    mock_growatt_classic_api.plant_info.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_RETRY

    # Several setup retries on Home Assistant's short backoff
    for _ in range(10):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_growatt_classic_api.plant_info.side_effect = None
    mock_growatt_classic_api.plant_info.return_value = plant_info
    mock_growatt_classic_api.tlx_detail.return_value = tlx_detail(2100)
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.assert_called_once()
    assert hass.states.get(TLX_OUTPUT_POWER).state == "2100"


async def test_classic_api_reload_logs_in_again(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
) -> None:
    """Test a reload starts from a fresh login instead of the cached session."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    mock_growatt_classic_api.login.assert_called_once()

    await hass.config_entries.async_reload(mock_config_entry_classic.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    assert mock_growatt_classic_api.login.call_count == 2


@pytest.mark.usefixtures("freezer")
async def test_classic_session_cooldown_wins_over_relogin_interval(
    hass: HomeAssistant,
) -> None:
    """Test a renew after a 507 reports the cooldown, not the re-login interval."""
    api = Mock(server_url="https://openapi.growatt.com/")
    api.login.return_value = {"success": False, "msg": "507"}
    session = GrowattClassicSession(hass, api, "test_user", "test_password")

    with pytest.raises(GrowattLoginRateLimited):
        session.renew(0)
    # A second coordinator that saw the same dead session
    with pytest.raises(GrowattLoginRateLimited) as err:
        session.renew(0)

    assert err.value.retry_after == LOGIN_COOLDOWN.total_seconds()
    api.login.assert_called_once()


async def test_classic_session_cooldown_is_per_server(
    hass: HomeAssistant,
) -> None:
    """Test a 507 on one Growatt server does not block the same user elsewhere."""
    blocked_api = Mock(server_url="https://openapi.growatt.com/")
    blocked_api.login.return_value = {"success": False, "msg": "507"}
    other_api = Mock(server_url="https://openapi-au.growatt.com/")
    other_api.login.return_value = {"success": True}

    blocked = GrowattClassicSession(hass, blocked_api, "test_user", "test_password")
    other = GrowattClassicSession(hass, other_api, "test_user", "test_password")

    with pytest.raises(GrowattLoginRateLimited):
        blocked.login()
    assert other.login() == {"success": True}


async def test_classic_api_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test integration setup with Classic API (password auth)."""
    # Classic API doesn't support MIN devices - use TLX device instead
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # Verify Classic API login was called
    mock_growatt_classic_api.login.assert_called()

    # Verify device was created
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "TLX123456"), mock_config_entry_classic.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("config_data", "expected_auth_type"),
    [
        (
            {
                CONF_TOKEN: "test_token_123",
                CONF_URL: "https://openapi.growatt.com/",
                "plant_id": "plant_123",
            },
            AUTH_API_TOKEN,
        ),
        (
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_URL: "https://server.growatt.com/",
                "plant_id": "plant_456",
            },
            AUTH_PASSWORD,
        ),
    ],
)
@pytest.mark.usefixtures("mock_growatt_v1_api", "mock_growatt_classic_api")
async def test_migrate_config_without_auth_type(
    hass: HomeAssistant,
    config_data: dict[str, str],
    expected_auth_type: str,
) -> None:
    """Test migration adds auth_type field to legacy configs and bumps version.

    This test verifies that config entries created before auth_type was introduced
    are properly migrated by:
    - Adding CONF_AUTH_TYPE with the correct value (AUTH_API_TOKEN or AUTH_PASSWORD)
    - Bumping version from 1.0 to 1.1
    """
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        unique_id=config_data["plant_id"],
        version=1,
        minor_version=0,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify version was updated to 1.1
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Verify auth_type field was added during migration
    assert mock_config_entry.data[CONF_AUTH_TYPE] == expected_auth_type

    # Verify setup completed successfully after migration
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_migrate_legacy_config_no_auth_fields(
    hass: HomeAssistant,
) -> None:
    """Test migration succeeds but setup fails for config without auth fields."""
    # Create a config entry without any auth fields
    invalid_config = {
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_789",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=invalid_config,
        unique_id="plant_789",
        version=1,
        minor_version=0,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Migration succeeds (version bumped) but setup fails due to missing auth fields
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_login_exceptions(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test Classic API setup with login exceptions."""
    mock_growatt_classic_api.login.side_effect = exception

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("login_response", "expected_state"),
    [
        pytest.param(
            {"success": False, "msg": "502"},
            ConfigEntryState.SETUP_ERROR,
            id="invalid_auth",
        ),
        pytest.param(
            {"success": False, "msg": "Server maintenance"},
            ConfigEntryState.SETUP_ERROR,
            id="other_login_error",
        ),
        pytest.param(
            {"success": False, "msg": "507"},
            ConfigEntryState.SETUP_RETRY,
            id="rate_limited",
        ),
    ],
)
async def test_classic_api_login_failures(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    login_response: dict,
    expected_state: ConfigEntryState,
) -> None:
    """Test Classic API setup with login failures."""
    mock_growatt_classic_api.login.return_value = login_response

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is expected_state


async def test_classic_api_setup_skips_login_during_cooldown(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    mock_config_entry_classic: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup does not log in again until the 507 cooldown has passed."""
    mock_growatt_classic_api.login.return_value = {"success": False, "msg": "507"}

    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_RETRY

    await hass.config_entries.async_reload(mock_config_entry_classic.entry_id)
    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_RETRY
    mock_growatt_classic_api.login.assert_called_once()

    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 12345},
    }
    freezer.tick(LOGIN_COOLDOWN)
    await hass.config_entries.async_reload(mock_config_entry_classic.entry_id)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED
    assert mock_growatt_classic_api.login.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_device_list_exceptions(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    exception: Exception,
) -> None:
    """Test Classic API setup with device_list exceptions."""
    # Create a config entry that won't trigger migration
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_123",  # Specific ID to avoid migration
        },
        unique_id="plant_123",
    )

    # device_list raises exception during setup
    mock_growatt_classic_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_classic_api_device_list_no_devices(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test Classic API setup when device list returns no devices."""
    # Create a config entry that won't trigger migration
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_456",  # Specific ID to avoid migration
        },
        unique_id="plant_456",
    )

    # device_list returns empty list (no devices)
    mock_growatt_classic_api.device_list.return_value = []

    await setup_integration(hass, mock_config_entry)

    # Should still load successfully even with no devices
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.RequestException("Connection error"),
        json.decoder.JSONDecodeError("Invalid JSON", "", 0),
    ],
    ids=["network_error", "json_error"],
)
async def test_classic_api_device_list_errors(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test Classic API setup with device list errors."""
    mock_growatt_classic_api.device_list.side_effect = exception

    await setup_integration(hass, mock_config_entry_classic)

    assert mock_config_entry_classic.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_api_version(
    hass: HomeAssistant,
) -> None:
    """Test setup with unknown API version."""
    # Create a config entry with invalid auth type
    config = {
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_123",
        CONF_AUTH_TYPE: "unknown_auth",  # Invalid auth type
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_123",
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_classic_api_auto_select_plant(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic_default_plant: MockConfigEntry,
) -> None:
    """Test Classic API setup with default plant ID (auto-selects first plant)."""
    # Login succeeds and plant_list returns a plant
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "AUTO_PLANT_123", "plantName": "Auto Plant"}]
    }
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX999999", "deviceType": "tlx"}
    ]

    await setup_integration(hass, mock_config_entry_classic_default_plant)

    # Should be loaded successfully with auto-selected plant
    assert mock_config_entry_classic_default_plant.state is ConfigEntryState.LOADED


async def test_v1_api_unsupported_device_type(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test V1 API logs warning for unsupported device types (non-MIN)."""
    config = {
        CONF_TOKEN: "test_token_123",
        CONF_URL: "https://openapi.growatt.com/",
        "plant_id": "plant_123",
        CONF_AUTH_TYPE: AUTH_API_TOKEN,
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        unique_id="plant_123",
    )

    # Return mix of MIN (type 7) and other device types
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {"device_sn": "MIN123456", "type": 7},  # Supported (MIN)
            {"device_sn": "UNK999999", "type": 3},  # Unsupported
        ]
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Verify warning was logged for unsupported device
    assert "Device UNK999999 with type 3 not supported in Open API V1" in caplog.text


async def test_migrate_version_bump(
    hass: HomeAssistant,
    mock_growatt_classic_api,
) -> None:
    """Test migration from 1.0 to 1.1 resolves DEFAULT_PLANT_ID and bumps version.

    This test verifies that:
    - Migration successfully resolves DEFAULT_PLANT_ID ("0") to actual plant_id
    - Config entry version is bumped from 1.0 to 1.1
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    # Mock successful API responses for migration and setup
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "RESOLVED_PLANT_789", "plantName": "My Plant"}]
    }
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify version was updated to 1.1
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Verify plant_id was resolved to actual plant_id (not DEFAULT_PLANT_ID)
    assert mock_config_entry.data[CONF_PLANT_ID] == "RESOLVED_PLANT_789"

    # Verify setup completed successfully after migration
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_reuses_cached_api_from_migration(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setup reuses cached API instance from migration.

    This test verifies the rate limit optimization where:
    1. Migration calls login() and caches the authenticated API instance
    2. Setup retrieves and reuses the cached API (avoiding a second login())
    3. The cached API is removed after use (one-time use pattern)

    Without this caching, we would call login() twice within seconds:
        Migration: login() → plant_list()
        Setup:     login() → device_list()
    This would trigger Growatt API rate limiting (5-minute window per endpoint).

    With caching, we only call login() once:
        Migration: login() → plant_list() → [cache API]
        Setup:     [reuse API] → device_list()
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    # Mock successful API responses
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = {
        "data": [{"plantId": "RESOLVED_PLANT_789", "plantName": "My Plant"}]
    }
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    mock_growatt_classic_api.plant_info.return_value = {
        "deviceList": [],
        "totalEnergy": 1250.0,
        "todayEnergy": 12.5,
        "invTodayPpv": 2500,
        "plantMoneyText": "123.45/USD",
    }
    mock_growatt_classic_api.tlx_detail.return_value = {
        "data": {"deviceSn": "TLX123456"}
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration successfully resolved plant_id
    assert mock_config_entry.data[CONF_PLANT_ID] == "RESOLVED_PLANT_789"

    # Verify integration loaded successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify log message confirms API reuse (rate limit optimization)
    assert "Reusing logged-in Growatt session" in caplog.text

    # Verify login was called with correct credentials
    # Note: Coordinators also call login() during refresh, so we verify
    # the call was made but don't assert it was called exactly once
    mock_growatt_classic_api.login.assert_called_with("test_user", "test_password")

    # Verify plant_list was called only once (during migration, not during setup)
    # This confirms setup did NOT resolve plant_id again (optimization working)
    mock_growatt_classic_api.plant_list.assert_called_once_with(123456)


@pytest.mark.parametrize(
    ("login_mock", "reason"),
    [
        pytest.param(
            {"side_effect": requests.exceptions.RequestException("Network error")},
            "Failed to resolve the plant ID from the Growatt API",
            id="network_error",
        ),
        pytest.param(
            {"return_value": {"success": False, "msg": "507"}},
            "Growatt has temporarily blocked logins for this account after too"
            " many attempts (error 507). Home Assistant will try again automatically later",
            id="rate_limited",
        ),
    ],
)
async def test_migrate_failure_retries(
    hass: HomeAssistant,
    mock_growatt_classic_api: MagicMock,
    login_mock: dict[str, Any],
    reason: str,
) -> None:
    """Test migration is retried on API failure.

    When migration fails due to API errors (network issues, etc.),
    it should raise ConfigEntryNotReady and NOT bump the version, so
    Home Assistant retries the migration.
    """
    # Create a version 1.0 config entry with DEFAULT_PLANT_ID
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: DEFAULT_PLANT_ID,
            CONF_NAME: "Test Plant",
        },
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )

    mock_growatt_classic_api.login.configure_mock(**login_mock)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == reason

    # Verify version was NOT bumped (remains 1.0)
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 0

    # Verify plant_id was NOT changed (remains DEFAULT_PLANT_ID)
    assert mock_config_entry.data[CONF_PLANT_ID] == DEFAULT_PLANT_ID


@pytest.mark.parametrize(
    ("data", "plant_list", "reason"),
    [
        pytest.param(
            {
                CONF_AUTH_TYPE: AUTH_API_TOKEN,
                CONF_TOKEN: "test_token",
                CONF_PLANT_ID: DEFAULT_PLANT_ID,
            },
            None,
            "The configuration contains an invalid plant ID, reconfigure the"
            " integration",
            id="v1_api_default_plant_id",
        ),
        pytest.param(
            {
                CONF_AUTH_TYPE: AUTH_PASSWORD,
                CONF_USERNAME: "test_user",
                CONF_PLANT_ID: DEFAULT_PLANT_ID,
            },
            None,
            "The configuration is missing the username or password, reconfigure"
            " the integration",
            id="missing_credentials",
        ),
        pytest.param(
            {
                CONF_AUTH_TYPE: AUTH_PASSWORD,
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_PLANT_ID: DEFAULT_PLANT_ID,
            },
            {"data": []},
            "No plants found for Growatt account test_user",
            id="no_plants",
        ),
    ],
)
async def test_migrate_error(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    data: dict[str, str],
    plant_list: dict[str, list] | None,
    reason: str,
) -> None:
    """Test migration errors that cannot be recovered without user action."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id="plant_default",
        version=1,
        minor_version=0,
    )
    mock_growatt_classic_api.login.return_value = {
        "success": True,
        "user": {"id": 123456},
    }
    mock_growatt_classic_api.plant_list.return_value = plant_list

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_config_entry.reason == reason
    assert mock_config_entry.minor_version == 0


@pytest.mark.usefixtures("mock_growatt_classic_api")
async def test_migrate_already_migrated(
    hass: HomeAssistant,
) -> None:
    """Test migration is skipped for already migrated entries."""
    # Create a config entry already at version 1.1
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: "https://server.growatt.com/",
            CONF_PLANT_ID: "specific_plant_123",
        },
        unique_id="plant_specific",
        version=1,
        minor_version=1,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify version remains 1.1 (no change)
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 1

    # Plant ID should remain unchanged
    assert mock_config_entry.data[CONF_PLANT_ID] == "specific_plant_123"

    # Verify setup completed successfully
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_added(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new devices are dynamically added when discovered during a scan."""
    # Initially only MIN123456 device exists
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "MIN123456"), mock_config_entry.entry_id
        )
        is not None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "NEW456789"), mock_config_entry.entry_id
        )
        is None
    )

    # Mock a new device appearing in the device list
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {"device_sn": "MIN123456", "type": 7},
            {"device_sn": "NEW456789", "type": 7},
        ]
    }
    mock_growatt_v1_api.min_detail.return_value = {
        "deviceSn": "NEW456789",
        "acChargeEnable": 0,
    }

    # Trigger the periodic device scan
    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # New device should now be in the device registry
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "NEW456789"), mock_config_entry.entry_id
        )
        is not None
    )
    # New device should be in runtime_data
    assert "NEW456789" in mock_config_entry.runtime_data.devices
    # Entities for the new device should have been created via the dispatcher.
    # Verify multiple entity types to confirm end-to-end dynamic device support
    assert hass.states.get("switch.new456789_charge_from_grid") is not None
    # Additional check: verify entities exist in the entity registry
    new_device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "NEW456789"), mock_config_entry.entry_id
    )
    new_device_entities = er.async_entries_for_device(
        entity_registry, new_device_entry.id, include_disabled_entities=True
    )
    assert len(new_device_entities) > 0, "No entities created for new device"


@pytest.mark.usefixtures("init_integration")
async def test_stale_device_removed(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that stale devices are removed from the device registry during a scan."""
    # Initially MIN123456 device exists with entities in the state machine
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "MIN123456"), mock_config_entry.entry_id
        )
        is not None
    )
    assert hass.states.get("switch.min123456_charge_from_grid") is not None

    # Mock the device disappearing from the API
    mock_growatt_v1_api.device_list.return_value = {"devices": []}

    # Trigger the periodic device scan
    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The device should be removed from HA
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "MIN123456"), mock_config_entry.entry_id
        )
        is None
    )
    # The coordinator should be removed from runtime_data
    assert "MIN123456" not in mock_config_entry.runtime_data.devices
    # Orphaned entities must also be gone from the entity registry and state machine
    assert entity_registry.async_get("switch.min123456_charge_from_grid") is None
    assert hass.states.get("switch.min123456_charge_from_grid") is None


@pytest.mark.usefixtures("init_integration")
async def test_device_scan_error_is_silent(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that errors during device scan are handled gracefully without crashing."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Simulate a scan failure
    mock_growatt_v1_api.device_list.side_effect = growattServer.GrowattV1ApiError(
        message="Temporary error",
        error_code=growattServer.GrowattV1ApiErrorCode.RATE_LIMITED,
        error_msg="Temporary error",
    )

    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Integration should remain loaded - scan errors are non-fatal
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Existing device should still be present
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "MIN123456"), mock_config_entry.entry_id
        )
        is not None
    )


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_refresh_fails_is_skipped(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a new device whose first coordinator refresh fails is not added."""
    # Mock a new device appearing but its data endpoint failing
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [
            {"device_sn": "MIN123456", "type": 7},
            {"device_sn": "NEW456789", "type": 7},
        ]
    }

    def min_detail_side_effect(device_sn: str) -> dict:
        if device_sn == "NEW456789":
            raise growattServer.GrowattV1ApiError(
                message="Device not reachable",
                error_code=growattServer.GrowattV1ApiErrorCode.RATE_LIMITED,
                error_msg="Device not reachable",
            )
        return mock_growatt_v1_api.min_detail.return_value

    mock_growatt_v1_api.min_detail.side_effect = min_detail_side_effect

    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # New device should NOT be added — its refresh failed
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "NEW456789"), mock_config_entry.entry_id
        )
        is None
    )
    assert "NEW456789" not in mock_config_entry.runtime_data.devices
    # Existing device must be unaffected
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "MIN123456"), mock_config_entry.entry_id
        )
        is not None
    )


async def test_classic_api_device_scan(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the periodic device scan works correctly for Classic API (password auth).

    The scan must reuse the total coordinator's authenticated session (no extra login).
    """
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # Mock a new device appearing; reset device_list call count after setup
    # so we can assert the scan calls it exactly once.
    mock_growatt_classic_api.device_list.reset_mock()
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"},
        {"deviceSn": "TLX999999", "deviceType": "tlx"},
    ]
    mock_growatt_classic_api.tlx_detail.return_value = {
        "data": {"deviceSn": "TLX999999"}
    }

    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # New device should be added via the classic scan path
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "TLX999999"), mock_config_entry_classic.entry_id
        )
        is not None
    )
    assert "TLX999999" in mock_config_entry_classic.runtime_data.devices

    # The scan reuses the coordinator's API session — device_list must have been
    # called exactly once (by the scan itself, not a fresh login+list cycle).
    mock_growatt_classic_api.device_list.assert_called_once()


async def test_classic_api_stale_device_removed(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that stale devices are removed during a Classic API device scan."""
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]
    await setup_integration(hass, mock_config_entry_classic)
    assert mock_config_entry_classic.state is ConfigEntryState.LOADED

    # Verify device exists after setup
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "TLX123456"), mock_config_entry_classic.entry_id
        )
        is not None
    )
    assert "TLX123456" in mock_config_entry_classic.runtime_data.devices

    # Mock the device disappearing from the API
    mock_growatt_classic_api.device_list.return_value = []

    # Trigger the periodic device scan
    freezer.tick(DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # The device should be removed from HA
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "TLX123456"), mock_config_entry_classic.entry_id
        )
        is None
    )
    # The coordinator should be removed from runtime_data
    assert "TLX123456" not in mock_config_entry_classic.runtime_data.devices
