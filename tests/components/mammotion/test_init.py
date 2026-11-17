"""Tests for the Mammotion integration setup."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, create_autospec

from aiohttp import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
from pymammotion.aliyun.exceptions import CloudSetupError, DeviceOfflineException
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.device.handle import DeviceHandle
from pymammotion.http.model.http import UnauthorizedExceptionError
from pymammotion.transport import NoTransportAvailableError
from pymammotion.transport.base import (
    AuthError,
    LoginFailedError,
    ReLoginRequiredError,
    TransportType,
)
from pymammotion.utility.constant.device_constant import WorkMode
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from Tea.exceptions import RetryError, UnretryableException
from Tea.request import TeaRequest

from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.components.mammotion.const import (
    CONF_AEP_DATA,
    CONF_MAMMOTION_DEVICE_RECORDS,
    CONF_MAMMOTION_MQTT,
    DOMAIN,
)
from homeassistant.components.mammotion.coordinator import DEFAULT_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ACCOUNT_ID, ACCOUNT_NAME, DEFAULT_NAME, cloud_device, setup_integration

ENTITY_ID = "lawn_mower.luba"


def _retry_exhausted(inner: Exception) -> UnretryableException:
    """Return the error Tea raises once its retries of a network error are spent."""
    retry = RetryError(str(inner))
    retry.__context__ = inner
    return UnretryableException(TeaRequest(), retry)


def _stored_state(hass_storage: dict[str, Any], key: str, data: dict) -> None:
    """Store mower state as the integration would have written it."""
    hass_storage[key] = {"version": 1, "minor_version": 0, "key": key, "data": data}


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_mammotion.login_and_initiate_cloud.assert_awaited_once()
    assert mock_mammotion.login_and_initiate_cloud.call_args.args[:2] == (
        ACCOUNT_NAME,
        "password",
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mammotion.stop.assert_awaited_once()
    mock_mammotion.remove_device.assert_awaited_once_with(DEFAULT_NAME)


@pytest.mark.parametrize(
    ("error", "reauth_required", "expected_state", "expected_reauth_flows"),
    [
        pytest.param(
            ClientConnectorError(MagicMock(), OSError("boom")),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="client",
        ),
        pytest.param(
            ConnectionError("HTTP 503"),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="server_unavailable",
        ),
        pytest.param(TimeoutError, None, ConfigEntryState.SETUP_RETRY, 0, id="timeout"),
        pytest.param(
            CloudSetupError("no session"),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="cloud_setup",
        ),
        pytest.param(
            _retry_exhausted(OSError("network down")),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="retries_exhausted",
        ),
        pytest.param(
            UnretryableException(TeaRequest(), ValueError("bad response")),
            None,
            ConfigEntryState.SETUP_ERROR,
            0,
            id="unretryable",
        ),
        pytest.param(
            LoginFailedError(ACCOUNT_ID, "bad password"),
            None,
            ConfigEntryState.SETUP_ERROR,
            1,
            id="login_rejected",
        ),
        pytest.param(
            ReLoginRequiredError(ACCOUNT_ID, "refresh token rejected"),
            "refresh token rejected",
            ConfigEntryState.SETUP_ERROR,
            1,
            id="session_rejected",
        ),
        pytest.param(
            ReLoginRequiredError(ACCOUNT_ID, "transport gave up"),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="transport_refused",
        ),
        pytest.param(
            UnauthorizedExceptionError("token expired"),
            None,
            ConfigEntryState.SETUP_RETRY,
            0,
            id="unauthorized",
        ),
    ],
)
async def test_setup_login_failure(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    reauth_required: str | None,
    expected_state: ConfigEntryState,
    expected_reauth_flows: int,
) -> None:
    """Test a failed login is retried or reported, and the client is stopped.

    A client left running keeps its MQTT session, and the next attempt
    connects with the same client_id, so the broker rejects both.
    """
    mock_mammotion.login_and_initiate_cloud.side_effect = error
    mock_mammotion.reauth_required = reauth_required

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    assert (
        len(hass.config_entries.flow.async_progress_by_handler(DOMAIN))
        == expected_reauth_flows
    )
    mock_mammotion.stop.assert_awaited_once()


async def test_setup_retry_on_failed_refresh(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried, and the client stopped, when the first poll fails."""
    mock_mower_api.update.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_mower_api.mammotion.stop.assert_awaited_once()


@pytest.mark.parametrize(
    "cache",
    [
        pytest.param(
            {
                CONF_MAMMOTION_MQTT: {"host": "mqtt"},
                CONF_MAMMOTION_DEVICE_RECORDS: {"records": [DEFAULT_NAME]},
            },
            id="mammotion_mqtt",
        ),
        pytest.param({CONF_AEP_DATA: {"aep": "data"}}, id="aliyun"),
    ],
)
async def test_setup_restores_cached_credentials(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
    cache: dict[str, Any],
) -> None:
    """Test cached credentials are restored instead of logging in again."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, **cache}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_mammotion.restore_credentials.assert_awaited_once()
    assert mock_mammotion.restore_credentials.call_args.args[2] == dict(
        mock_config_entry.data
    )
    mock_mammotion.login_and_initiate_cloud.assert_not_awaited()


async def test_setup_persists_credentials(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the session the login produced is stored for the next start."""
    cache = {CONF_AEP_DATA: {"aep": "data"}}
    mock_mammotion.to_cache.return_value = cache

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.data[CONF_AEP_DATA] == cache[CONF_AEP_DATA]


async def test_rotated_credentials_persisted(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test credentials the library rotates are written to the entry."""
    await setup_integration(hass, mock_config_entry)
    mock_mammotion.to_cache.return_value = {CONF_AEP_DATA: {"aep": "rotated"}}

    await mock_mammotion.on_credentials_updated()

    assert mock_config_entry.data[CONF_AEP_DATA] == {"aep": "rotated"}


async def test_unrecoverable_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a dead cloud session prompts for reauth once."""
    await setup_integration(hass, mock_config_entry)
    callback = mock_mammotion.on_unrecoverable_auth_error
    error = ReLoginRequiredError(ACCOUNT_ID, "refresh token rejected")

    await callback(ACCOUNT_ID, TransportType.CLOUD_ALIYUN, error)
    await callback(ACCOUNT_ID, TransportType.CLOUD_MAMMOTION, error)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert "Mammotion cloud authentication failed" in caplog.text


@pytest.mark.parametrize(
    "mock_cloud_devices",
    [pytest.param([cloud_device("RTK-ABC123")], id="rtk_base_station")],
)
async def test_unsupported_device_not_added(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_cloud_devices: list[Device],
) -> None:
    """Test devices that are not mowers are left out."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_mower_api.update.assert_not_awaited()


MOWING_STATE = MowingDevice.from_dict(
    {"report_data": {"dev": {"sys_status": WorkMode.MODE_WORKING}}}
)


@pytest.mark.parametrize(
    ("stored", "expected_restored", "expected_state"),
    [
        pytest.param(
            MOWING_STATE.to_dict(),
            MOWING_STATE,
            LawnMowerActivity.MOWING,
            id="restored",
        ),
        pytest.param(
            {"report_data": {"dev": {"sys_status": "corrupt"}}},
            MowingDevice(),
            STATE_UNKNOWN,
            id="corrupt",
        ),
    ],
)
async def test_state_restored_from_store(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    stored: dict[str, Any],
    expected_restored: MowingDevice,
    expected_state: str,
) -> None:
    """Test the stored state is shown until an offline mower reports again."""
    handle = create_autospec(DeviceHandle, instance=True)
    mock_mower_api.mammotion.mower.return_value = handle
    mock_mower_api.update.side_effect = DeviceOfflineException(1, "iot")
    _stored_state(
        hass_storage, f"{DOMAIN}.{mock_config_entry.entry_id}", {DEFAULT_NAME: stored}
    )

    await setup_integration(hass, mock_config_entry)

    handle.restore_device.assert_called_once_with(expected_restored)
    assert hass.states.get(ENTITY_ID).state == expected_state


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(DeviceOfflineException(1, "iot"), id="offline"),
        pytest.param(NoTransportAvailableError("no transport"), id="no_transport"),
    ],
)
async def test_poll_keeps_state_while_unreachable(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test a poll that cannot reach the mower keeps the last state."""
    mock_mowing_device.report_data.dev.sys_status = WorkMode.MODE_WORKING
    await setup_integration(hass, mock_config_entry)

    mock_mower_api.update.side_effect = error
    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_mower_api.update.await_count == 2
    assert hass.states.get(ENTITY_ID).state == LawnMowerActivity.MOWING


async def test_poll_without_data_makes_entity_unavailable(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll that returns nothing marks the mower unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_mower_api.update.return_value = None
    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_mower_api")
async def test_state_persisted_on_final_write(
    hass: HomeAssistant,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test mower state is not written on every poll but on Home Assistant stop."""
    mock_mowing_device.report_data.dev.sys_status = WorkMode.MODE_WORKING
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"

    assert storage_key not in hass_storage

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert storage_key not in hass_storage

    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert hass_storage[storage_key]["data"] == {
        DEFAULT_NAME: mock_mowing_device.to_dict()
    }


@pytest.mark.usefixtures("mock_mower_api")
async def test_unload_persists_state_and_credentials(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test pending mower state and the session are saved when the entry unloads."""
    await setup_integration(hass, mock_config_entry)
    storage_key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    assert storage_key not in hass_storage
    mock_mammotion.to_cache.reset_mock()
    mock_mammotion.to_cache.return_value = {CONF_AEP_DATA: {"aep": "latest"}}

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DEFAULT_NAME in hass_storage[storage_key]["data"]
    assert mock_config_entry.data[CONF_AEP_DATA] == {"aep": "latest"}
    mock_mammotion.to_cache.assert_called_once()


@pytest.mark.usefixtures("mock_mower_api")
async def test_remove_entry_keeps_other_entry_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test removing an entry leaves the stored state of other entries intact."""
    other_key = f"{DOMAIN}.other_entry_id"
    _stored_state(hass_storage, other_key, {"Luba-OTHER": MowingDevice().to_dict()})
    await setup_integration(hass, mock_config_entry)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{mock_config_entry.entry_id}" in hass_storage

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert f"{DOMAIN}.{mock_config_entry.entry_id}" not in hass_storage
    assert other_key in hass_storage


async def test_client_stopped_before_unload_returns(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is torn down before unload completes.

    A reload sets the entry up again as soon as unload returns. If the old
    client is still holding its MQTT session, both sessions connect with the
    same client_id and the broker rejects them.
    """
    await setup_integration(hass, mock_config_entry)

    stopped = False

    async def _stop() -> None:
        # Suspend, as disconnecting a real MQTT transport does.
        await asyncio.sleep(0)
        nonlocal stopped
        stopped = True

    mock_mammotion.stop.side_effect = _stop

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert stopped, "unload returned while the client still held its connection"


async def test_reload_does_not_overlap_clients(
    hass: HomeAssistant,
    mock_mammotion: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reload stops the old client before the new one logs in."""
    await setup_integration(hass, mock_config_entry)

    call_order: list[str] = []

    async def _stop() -> None:
        await asyncio.sleep(0)
        call_order.append("stop")

    async def _login(*args: Any, **kwargs: Any) -> None:
        call_order.append("login")

    mock_mammotion.stop.side_effect = _stop
    mock_mammotion.login_and_initiate_cloud.side_effect = _login

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert call_order == ["stop", "login"]


async def test_auth_error_while_polling_starts_reauth(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth failure during a poll prompts for reauth."""
    await setup_integration(hass, mock_config_entry)

    mock_mower_api.update.side_effect = AuthError("token rejected")

    freezer.tick(DEFAULT_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def _remove_device(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, device_id: str
) -> dict[str, Any]:
    """Ask Home Assistant to remove a device and return the response."""
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove", "device_id": device_id}
    )
    return await client.receive_json()


@pytest.mark.usefixtures("mock_mower_api")
async def test_remove_live_mower_refused(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a mower still in the account cannot be removed."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEFAULT_NAME), mock_config_entry.entry_id
    )
    assert device is not None

    response = await _remove_device(hass, hass_ws_client, device.id)

    assert not response["success"]
    assert device_registry.async_get(device.id) is not None


@pytest.mark.usefixtures("mock_mower_api")
async def test_remove_orphaned_mower(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a mower that has left the account can be removed."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "Luba-GONE")},
    )

    response = await _remove_device(hass, hass_ws_client, device.id)

    assert response["success"]
    assert device_registry.async_get(device.id) is None
