"""Test the initialization of Yardian."""

import datetime as dt
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import setup_integration

ZONE_SWITCH_ENTITY_ID = "switch.zone_1"


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(NetworkException("offline"), id="network"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_setup_retries_client_creation(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_yardian_client_create: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test scheduled setup retries recover after model detection fails."""
    mock_yardian_client_create.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason == "Failed to connect"
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_domain == DOMAIN
    session = async_get_clientsession(hass)
    mock_yardian_client_create.assert_awaited_once_with(
        session,
        mock_config_entry.data[CONF_HOST],
        token=mock_config_entry.data[CONF_ACCESS_TOKEN],
    )
    mock_yardian_client.fetch_device_state.assert_not_awaited()
    mock_yardian_client.fetch_oper_info.assert_not_awaited()
    assert not hass.states.async_all()
    assert not session.closed
    assert not hass.config_entries.flow.async_progress()

    mock_yardian_client_create.side_effect = None
    freezer.tick(dt.timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_yardian_client_create.await_count == 2
    mock_yardian_client_create.assert_awaited_with(
        session,
        mock_config_entry.data[CONF_HOST],
        token=mock_config_entry.data[CONF_ACCESS_TOKEN],
    )
    mock_yardian_client.fetch_device_state.assert_awaited_once()
    mock_yardian_client.fetch_oper_info.assert_awaited_once()
    assert hass.states.get(ZONE_SWITCH_ENTITY_ID).state == STATE_ON
    assert not session.closed


@pytest.mark.parametrize(
    ("exception", "reason", "translation_key", "reauth_count"),
    [
        pytest.param(
            NotAuthorizedException(),
            "Invalid authentication",
            "invalid_auth",
            1,
            id="auth",
        ),
        pytest.param(ValueError("unexpected"), None, None, 0, id="unexpected"),
    ],
)
async def test_client_creation_fatal_error(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_yardian_client_create: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    reason: str | None,
    translation_key: str | None,
    reauth_count: int,
) -> None:
    """Test authentication and unexpected errors do not schedule retries."""
    mock_yardian_client_create.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == reason
    assert mock_config_entry.error_reason_translation_key == translation_key
    mock_yardian_client.fetch_device_state.assert_not_awaited()
    mock_yardian_client.fetch_oper_info.assert_not_awaited()
    assert not hass.states.async_all()
    assert len(hass.config_entries.flow.async_progress()) == reauth_count

    freezer.tick(dt.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_yardian_client_create.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("exception", "entry_state", "reauth_count"),
    [
        pytest.param(
            NotAuthorizedException, ConfigEntryState.SETUP_ERROR, 1, id="auth"
        ),
        pytest.param(TimeoutError, ConfigEntryState.SETUP_RETRY, 0, id="timeout"),
        pytest.param(NetworkException, ConfigEntryState.SETUP_RETRY, 0, id="network"),
        pytest.param(Exception, ConfigEntryState.SETUP_RETRY, 0, id="unexpected"),
    ],
)
@pytest.mark.parametrize("method", ["fetch_device_state", "fetch_oper_info"])
async def test_setup_unauthorized(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    entry_state: ConfigEntryState,
    reauth_count: int,
    method: str,
) -> None:
    """Test setup when unauthorized."""
    getattr(mock_yardian_client, method).side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is entry_state
    assert len(hass.config_entries.flow.async_progress()) == reauth_count


async def test_client_rejects_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the real client's explicit token rejection starts reauthentication."""
    aioclient_mock.get("http://1.2.3.4:880/API_GET_DEVICEINFO", json={"iCode": -1000})
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "invalid_auth"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("method", ["fetch_device_state", "fetch_oper_info"])
async def test_update_auth_failure_and_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test authentication failures recover without replacing entities or devices."""
    await setup_integration(hass, mock_config_entry)
    original_data = dict(mock_config_entry.data)
    original_options = dict(mock_config_entry.options)
    entity = entity_registry.async_get(ZONE_SWITCH_ENTITY_ID)
    assert entity is not None
    entity_registry.async_update_entity(entity.entity_id, name="Garden sprinkler")
    original_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    original_devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    failing_method = getattr(mock_yardian_client, method)
    failing_method.side_effect = NotAuthorizedException
    freezer.tick(dt.timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not mock_config_entry.runtime_data.last_update_success
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    failing_method.side_effect = None
    mock_yardian_client.fetch_device_info.return_value = {"yid": "yid123"}
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_ACCESS_TOKEN: "replacement_token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.unique_id == "yid123"
    assert mock_config_entry.options == original_options
    assert mock_config_entry.data == original_data | {
        CONF_ACCESS_TOKEN: "replacement_token"
    }
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == original_entities
    )
    assert (
        dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
        == original_devices
    )
    assert entity_registry.async_get(entity.entity_id).name == "Garden sprinkler"


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(NetworkException, id="network"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
@pytest.mark.parametrize("method", ["fetch_device_state", "fetch_oper_info"])
async def test_update_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    exception: type[Exception],
) -> None:
    """Test transient polling errors recover on the next update without reauth."""
    await setup_integration(hass, mock_config_entry)
    failing_method = getattr(mock_yardian_client, method)
    failing_method.side_effect = exception
    freezer.tick(dt.timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.last_update_success
    assert not hass.config_entries.flow.async_progress()

    failing_method.side_effect = None
    freezer.tick(dt.timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.last_update_success
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_yardian_client", "switch_platform_only")
async def test_zone_device_via_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that zone child devices link to the main device via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "yid123"), mock_config_entry.entry_id
    )
    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "yid123_0"), mock_config_entry.entry_id
    )

    assert main_device is not None
    assert zone_device is not None
    assert zone_device.via_device_id == main_device.id
