"""Define tests for the Vodafone Station coordinator."""

from json import JSONDecodeError
import logging
from unittest.mock import AsyncMock, call, create_autospec, patch

from aiohttp import ClientSession
from aiovodafone.api import VodafoneStationDevice
from aiovodafone.exceptions import (
    AlreadyLogged,
    CannotAuthenticate,
    GenericResponseError,
    VodafoneError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.vodafone_station.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration
from .const import DEVICE_1_HOST, DEVICE_1_MAC, DEVICE_2_HOST, DEVICE_2_MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_device_cleanup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Device cleanup on coordinator update."""

    caplog.set_level(logging.DEBUG)
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, DEVICE_1_MAC)},
        name=DEVICE_1_HOST,
    )
    assert device is not None

    device_tracker = f"device_tracker.{DEVICE_1_HOST}"

    assert hass.states.get(device_tracker)

    mock_vodafone_station_router.get_devices_data.return_value = {
        DEVICE_2_MAC: VodafoneStationDevice(
            connected=True,
            connection_type="lan",
            ip_address="192.168.1.11",
            name=DEVICE_2_HOST,
            mac=DEVICE_2_MAC,
            type="desktop",
            wifi="",
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(device_tracker) is None
    assert f"Skipping entity {DEVICE_2_HOST}" in caplog.text

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, DEVICE_1_MAC), mock_config_entry.entry_id
        )
        is None
    )
    assert f"Removing device: {DEVICE_1_HOST}" in caplog.text


@pytest.mark.parametrize(
    ("error", "expected_init_calls", "expected_session_calls"),
    [
        (VodafoneError("Generic error"), 1, 1),
        (
            JSONDecodeError("Invalid JSON", "<html>stale session</html>", 0),
            2,
            2,
        ),
    ],
)
async def test_coordinator_exceptions(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_init_calls: int,
    expected_session_calls: int,
) -> None:
    """Test exception handling during update: setup retry, plus session reinit for stale sessions."""
    mock_vodafone_station_router.get_devices_data.side_effect = error

    new_session = create_autospec(ClientSession, instance=True)
    with (
        patch(
            "homeassistant.components.vodafone_station.coordinator.init_device_class",
            return_value=mock_vodafone_station_router,
        ) as mock_init_device_class,
        patch(
            "homeassistant.components.vodafone_station.coordinator.async_client_session",
            AsyncMock(return_value=new_session),
        ) as mock_async_client_session,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        assert mock_init_device_class.call_count == expected_init_calls
        assert mock_async_client_session.await_count == expected_session_calls
        assert mock_init_device_class.call_args.args[2] == mock_config_entry.data
        assert mock_init_device_class.call_args.args[3] == new_session


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("get_devices_data", id="devices"),
        pytest.param("get_sensor_data", id="sensors"),
        pytest.param("get_wifi_data", id="wifi"),
    ],
)
async def test_session_relogin(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Recover from server-side session expiry despite remaining cookies."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._session.cookie_jar.update_cookies(
        {"session": "expired"}, response_url=coordinator.api.base_url
    )
    mock_vodafone_station_router.login.reset_mock()
    mock_vodafone_station_router.get_devices_data.reset_mock()
    failing_method = getattr(mock_vodafone_station_router, method)
    failing_method.side_effect = [
        CannotAuthenticate(),
        CannotAuthenticate(),
        failing_method.return_value,
    ]

    with (
        patch("homeassistant.components.vodafone_station.coordinator.asyncio.sleep"),
        patch.object(mock_config_entry, "async_start_reauth_if_available") as reauth,
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator._unsub_refresh is not None
    mock_vodafone_station_router.login.assert_awaited_once_with()
    assert mock_vodafone_station_router.get_devices_data.await_count == 3
    reauth.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected_exception", "reauth_count", "retry_login_count"),
    [
        pytest.param(CannotAuthenticate(), ConfigEntryAuthFailed, 1, 3, id="auth"),
        pytest.param(VodafoneError(), UpdateFailed, 0, 1, id="api"),
        pytest.param(TimeoutError(), TimeoutError, 0, 1, id="timeout"),
    ],
)
@pytest.mark.parametrize("failure_stage", ["login", "retry"])
async def test_session_relogin_failure(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_exception: type[Exception],
    reauth_count: int,
    retry_login_count: int,
    failure_stage: str,
) -> None:
    """Bound session recovery and propagate non-retryable login failures."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._session.cookie_jar.update_cookies(
        {"session": "expired"}, response_url=coordinator.api.base_url
    )
    mock_vodafone_station_router.login.reset_mock()
    mock_vodafone_station_router.get_devices_data.side_effect = [
        CannotAuthenticate(),
        CannotAuthenticate(),
        *[error] * 3,
    ]
    mock_vodafone_station_router.login.side_effect = {
        "login": error,
        "retry": None,
    }[failure_stage]

    with (
        patch("homeassistant.components.vodafone_station.coordinator.asyncio.sleep"),
        patch.object(mock_config_entry, "async_start_reauth_if_available") as reauth,
    ):
        await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, expected_exception)
    assert mock_vodafone_station_router.login.await_count == retry_login_count
    assert reauth.call_count == reauth_count


async def test_initial_login_auth_failure(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Do not retry rejected credentials during initial login."""
    mock_vodafone_station_router.login.side_effect = CannotAuthenticate()
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_vodafone_station_router.login.assert_awaited_once_with()
    mock_vodafone_station_router.get_devices_data.assert_not_awaited()


@pytest.mark.parametrize(
    "method", ["get_devices_data", "get_sensor_data", "get_wifi_data"]
)
@pytest.mark.parametrize(
    ("errors", "login_count", "success"),
    [
        pytest.param([GenericResponseError()], 0, True, id="response"),
        pytest.param([CannotAuthenticate()], 0, True, id="auth-existing-session"),
        pytest.param([CannotAuthenticate()] * 2, 1, True, id="auth-auth"),
        pytest.param([GenericResponseError()] * 5, 0, False, id="persistent"),
        pytest.param([GenericResponseError()] * 4, 0, True, id="last-attempt"),
        pytest.param(
            [CannotAuthenticate(), GenericResponseError()], 0, True, id="auth-response"
        ),
        pytest.param(
            [GenericResponseError(), CannotAuthenticate()], 0, True, id="response-auth"
        ),
        pytest.param([AlreadyLogged()], 0, True, id="already-logged"),
        pytest.param([AlreadyLogged()] * 5, 0, False, id="already-logged-persistent"),
        pytest.param(
            [AlreadyLogged(), GenericResponseError()],
            0,
            True,
            id="already-logged-response",
        ),
    ],
)
async def test_transient_response_retry(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    errors: list[Exception],
    login_count: int,
    success: bool,
) -> None:
    """Share five attempts with increasing delays and re-login only for auth errors."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._session.cookie_jar.update_cookies(
        {"session": "present"}, response_url=coordinator.api.base_url
    )
    mock_vodafone_station_router.login.reset_mock()
    failing_method = getattr(mock_vodafone_station_router, method)
    failing_method.reset_mock()
    failing_method.side_effect = [*errors, failing_method.return_value]

    with (
        patch(
            "homeassistant.components.vodafone_station.coordinator.asyncio.sleep"
        ) as sleep,
        patch.object(mock_config_entry, "async_start_reauth_if_available") as reauth,
    ):
        await coordinator.async_refresh()

    assert sleep.await_args_list == [
        call(delay) for delay in [2, 4, 6, 8][: len(errors)]
    ]
    assert coordinator.last_update_success is success
    assert failing_method.await_count == len(errors) + int(success)
    assert mock_vodafone_station_router.login.await_args_list == [call()] * login_count
    reauth.assert_not_called()
    assert coordinator._unsub_refresh is not None


@pytest.mark.parametrize(
    "stage",
    [
        pytest.param("initial", id="initial-login"),
        pytest.param("retry", id="retry-login"),
    ],
)
@pytest.mark.parametrize(
    ("login_results", "success", "recovery_attempts"),
    [
        pytest.param([AlreadyLogged(), True], True, 1, id="recovered"),
        pytest.param([AlreadyLogged(), AlreadyLogged()], False, 3, id="persistent"),
    ],
)
async def test_already_logged_login(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    stage: str,
    login_results: list[Exception | bool],
    success: bool,
    recovery_attempts: int,
) -> None:
    """Retry an occupied login once with force logout."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._session.cookie_jar.clear()
    mock_vodafone_station_router.login.reset_mock()
    mock_vodafone_station_router.login.side_effect = {
        "initial": login_results,
        "retry": [True, *login_results, *login_results, *login_results],
    }[stage]
    mock_vodafone_station_router.get_devices_data.side_effect = {
        "initial": [mock_vodafone_station_router.get_devices_data.return_value],
        "retry": [
            CannotAuthenticate(),
            CannotAuthenticate(),
            mock_vodafone_station_router.get_devices_data.return_value,
        ],
    }[stage]

    with (
        patch("homeassistant.components.vodafone_station.coordinator.asyncio.sleep"),
        patch.object(mock_config_entry, "async_start_reauth_if_available") as reauth,
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is success
    assert (
        mock_vodafone_station_router.login.await_args_list
        == {
            "initial": [call(), call(force_logout=True)],
            "retry": [
                call(),
                *([call(), call(force_logout=True)] * recovery_attempts),
            ],
        }[stage]
    )
    reauth.assert_not_called()


@pytest.mark.parametrize(
    "login_error",
    [
        pytest.param(CannotAuthenticate(), id="menu-401"),
        pytest.param(GenericResponseError(), id="menu-response"),
    ],
)
async def test_recovery_after_login_error(
    hass: HomeAssistant,
    mock_vodafone_station_router: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    login_error: Exception,
) -> None:
    """Recover when the menu request fails during a recovery login."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    coordinator._session.cookie_jar.update_cookies(
        {"session": "expired"}, response_url=coordinator.api.base_url
    )
    mock_vodafone_station_router.login.reset_mock()
    mock_vodafone_station_router.login.side_effect = [True, login_error, True]
    devices = mock_vodafone_station_router.get_devices_data
    devices.reset_mock()
    devices.side_effect = [
        CannotAuthenticate(),
        CannotAuthenticate(),
        CannotAuthenticate(),
        devices.return_value,
    ]
    with (
        patch(
            "homeassistant.components.vodafone_station.coordinator.asyncio.sleep"
        ) as sleep,
        patch.object(mock_config_entry, "async_start_reauth_if_available") as reauth,
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator._unsub_refresh is not None
    assert devices.await_count == 4
    assert mock_vodafone_station_router.login.await_count == 3
    assert sleep.await_args_list == [call(2), call(4), call(6), call(8)]
    assert "Data recovery succeeded on attempt 5 using re-login" in caplog.text
    reauth.assert_not_called()
