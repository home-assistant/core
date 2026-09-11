"""Tests for the Alexa Devices integration."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from aioamazondevices.exceptions import CannotConnect, CannotRetrieveData
from aioamazondevices.structures import AmazonListInfo, AmazonListType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_DEVICE_1_SN, TEST_PASSWORD, TEST_USER_ID, TEST_USERNAME

from tests.common import MockConfigEntry


def _fail_todo_list_items(client: AsyncMock, error: Exception) -> None:
    """Make the todo list items sync fail."""
    client.todo_lists = [
        AmazonListInfo(id="shopping_list_id", name=None, list_type=AmazonListType.SHOP)
    ]
    client.get_todo_list_items.side_effect = error


def _fail_history_state(client: AsyncMock, error: Exception) -> None:
    """Make the history state sync fail."""
    client.sync_history_state.side_effect = error


def _fail_media_state(client: AsyncMock, error: Exception) -> None:
    """Make the media state sync fail."""
    client.sync_media_state.side_effect = error


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE_1_SN), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("minor_version", "extra_data"),
    [
        # Standard migration case
        (
            1,
            {
                CONF_COUNTRY: "US",
                CONF_LOGIN_DATA: {
                    "session": "test-session",
                },
            },
        ),
        # Edge case #1: no country, site already in login data, minor version 1
        (
            1,
            {
                CONF_LOGIN_DATA: {
                    "session": "test-session",
                    CONF_SITE: "https://www.amazon.com",
                },
            },
        ),
        # Edge case #2: no country, site in data (wrong place), minor version 1
        (
            1,
            {
                CONF_SITE: "https://www.amazon.com",
                CONF_LOGIN_DATA: {
                    "session": "test-session",
                },
            },
        ),
        # Edge case #3: no country, site already in login data, minor version 2
        (
            2,
            {
                CONF_LOGIN_DATA: {
                    "session": "test-session",
                    CONF_SITE: "https://www.amazon.com",
                },
            },
        ),
        # Edge case #4: no country, site in data (wrong place), minor version 2
        (
            2,
            {
                CONF_SITE: "https://www.amazon.com",
                CONF_LOGIN_DATA: {
                    "session": "test-session",
                },
            },
        ),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    minor_version: int,
    extra_data: dict[str, str],
) -> None:
    """Test successful migration of entry data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Amazon Test Account",
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            **(extra_data),
        },
        unique_id=TEST_USER_ID,
        version=1,
        minor_version=minor_version,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.minor_version == 3
    assert config_entry.data[CONF_LOGIN_DATA][CONF_SITE] == "https://www.amazon.com"


async def test_migrate_future_version_returns_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration failure for downgraded future config entry version."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        entry_id=mock_config_entry.entry_id,
        version=2,
        minor_version=0,
    )

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_http2_reauth_required(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HTTP/2 re-authentication triggers a reauth flow."""
    await setup_integration(hass, mock_config_entry)

    on_reauth_required = (
        mock_amazon_devices_client.start_http2_processing.call_args.kwargs[
            "on_reauth_required"
        ]
    )
    await on_reauth_required()
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_http2_reauth_callback_triggers_reauth(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on_reauth_required callback passed to start_http2_processing triggers reauth."""
    captured_callback = None
    http2_task: asyncio.Task | None = None

    async def capture_callback(_client, on_reauth_required=None) -> asyncio.Task:
        nonlocal captured_callback, http2_task
        captured_callback = on_reauth_required
        http2_task = hass.loop.create_task(asyncio.sleep(3600))
        return http2_task

    mock_amazon_devices_client.start_http2_processing.side_effect = capture_callback

    with patch.object(mock_config_entry, "async_start_reauth") as mock_reauth:
        await setup_integration(hass, mock_config_entry)

        assert captured_callback is not None
        await captured_callback()

    mock_reauth.assert_called_once_with(hass)

    assert http2_task is not None
    http2_task.cancel()
    await asyncio.gather(http2_task, return_exceptions=True)


async def test_http2_stop_processing_called_on_unload(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop_http2_processing is called on unload."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_amazon_devices_client.stop_http2_processing.assert_awaited_once()


async def test_http2_stop_processing_called_on_shutdown(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop_http2_processing is awaited when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_amazon_devices_client.stop_http2_processing.assert_awaited_once()


@pytest.mark.parametrize(
    ("configure_failure", "invoked_method"),
    [
        (_fail_todo_list_items, "sync_todo_list_items"),
        (_fail_history_state, "sync_history_state"),
        (_fail_media_state, "sync_media_state"),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            CannotConnect("429 - Too Many Requests"),
            id="http_429_too_many_requests",
        ),
        pytest.param(
            CannotRetrieveData("503 - Service Unavailable"),
            id="http_503_service_unavailable",
        ),
    ],
)
async def test_initial_sync_amazon_api_failure_does_not_block_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    configure_failure: Callable[[AsyncMock, Exception], None],
    invoked_method: str,
    error: Exception,
) -> None:
    """Test a failing initial sync call is logged but does not block setup."""
    configure_failure(mock_amazon_devices_client, error)

    await setup_integration(hass, mock_config_entry)

    assert f"Initial sync failed for {invoked_method}:" in caplog.text
    assert str(error) in caplog.text
    assert (
        "Data may be missing or incomplete until updates are pushed by Amazon"
        in caplog.text
    )

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_initial_sync_failure_does_not_prevent_other_syncs(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failing initial sync call does not stop the remaining sync calls."""
    mock_amazon_devices_client.todo_lists = [
        AmazonListInfo(id="shopping_list_id", name=None, list_type=AmazonListType.SHOP)
    ]
    mock_amazon_devices_client.get_todo_list_items.return_value = {}
    mock_amazon_devices_client.sync_history_state.side_effect = CannotConnect(
        "429 - Too Many Requests"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_amazon_devices_client.get_todo_list_items.assert_awaited_once()
    mock_amazon_devices_client.sync_media_state.assert_awaited_once()
