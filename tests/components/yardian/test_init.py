"""Test the initialization of Yardian."""

import datetime as dt
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_ON
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr
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

    freezer.tick(dt.timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_yardian_client_create.await_count == 2
    mock_yardian_client.fetch_device_state.assert_not_awaited()
    mock_yardian_client.fetch_oper_info.assert_not_awaited()
    assert not hass.states.async_all()

    mock_yardian_client_create.side_effect = None
    freezer.tick(dt.timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_yardian_client_create.await_count == 3
    mock_yardian_client.fetch_device_state.assert_awaited_once()
    mock_yardian_client.fetch_oper_info.assert_awaited_once()
    assert hass.states.get(ZONE_SWITCH_ENTITY_ID).state == STATE_ON
    assert not session.closed


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(NetworkException("offline"), id="network"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_startup_retries_client_creation(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_yardian_client_create: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test a setup failure before startup retries when Home Assistant starts."""
    hass.set_state(CoreState.not_running)
    mock_yardian_client_create.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_yardian_client_create.assert_awaited_once()
    mock_yardian_client.fetch_device_state.assert_not_awaited()
    mock_yardian_client.fetch_oper_info.assert_not_awaited()
    assert not hass.states.async_all()

    mock_yardian_client_create.side_effect = None
    freezer.tick(dt.timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_yardian_client_create.assert_awaited_once()

    await hass.async_start()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_yardian_client_create.await_count == 2
    mock_yardian_client.fetch_device_state.assert_awaited_once()
    mock_yardian_client.fetch_oper_info.assert_awaited_once()
    assert hass.states.get(ZONE_SWITCH_ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(NotAuthorizedException(), "Invalid access token", id="auth"),
        pytest.param(ValueError("unexpected"), None, id="unexpected"),
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
) -> None:
    """Test authentication and unexpected errors do not schedule retries."""
    mock_yardian_client_create.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason == reason
    mock_yardian_client.fetch_device_state.assert_not_awaited()
    mock_yardian_client.fetch_oper_info.assert_not_awaited()
    assert not hass.states.async_all()

    freezer.tick(dt.timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_yardian_client_create.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (NotAuthorizedException, ConfigEntryState.SETUP_ERROR),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (NetworkException, ConfigEntryState.SETUP_RETRY),
        (Exception, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_unauthorized(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test setup when unauthorized."""
    mock_yardian_client.fetch_device_state.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is entry_state


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
