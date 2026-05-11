"""Tests for the Alexa Devices integration."""

import asyncio
from unittest.mock import ANY, AsyncMock, patch

from aioamazondevices.exceptions import CannotAuthenticate, CannotConnect
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import TEST_DEVICE_1_SN, TEST_PASSWORD, TEST_USER_ID, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)}
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


async def test_http2_task_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HTTP2 auth failure triggers reauth flow."""
    failed_task: asyncio.Future[None] = hass.loop.create_future()
    failed_task.set_exception(CannotAuthenticate("auth failed"))
    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: failed_task
    )

    with (
        patch("homeassistant.components.alexa_devices._LOGGER.error") as mock_error,
        patch.object(mock_config_entry, "async_start_reauth") as mock_reauth,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_error.assert_called_once_with(
        "HTTP2 auth failure", exc_info=(CannotAuthenticate, ANY, ANY)
    )
    mock_reauth.assert_called_once_with(hass)


async def test_http2_task_connection_failure_triggers_reload(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HTTP2 connection failure schedules reload."""
    failed_task: asyncio.Future[None] = hass.loop.create_future()
    failed_task.set_exception(CannotConnect("connection failed"))
    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: failed_task
    )

    with (
        patch("homeassistant.components.alexa_devices._LOGGER.warning") as mock_warning,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_warning.assert_called_once_with(
        "HTTP2 connection failure, scheduling reload",
        exc_info=(CannotConnect, ANY, ANY),
    )
    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_http2_task_unexpected_failure_triggers_reload(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unexpected HTTP2 failure schedules reload."""
    failed_task: asyncio.Future[None] = hass.loop.create_future()
    failed_task.set_exception(RuntimeError("boom"))
    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: failed_task
    )

    with (
        patch("homeassistant.components.alexa_devices._LOGGER.error") as mock_error,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_error.assert_called_once_with(
        "Unexpected HTTP2 failure, scheduling reload", exc_info=(RuntimeError, ANY, ANY)
    )
    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_http2_task_exception_group_is_unwrapped(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ExceptionGroup from TaskGroup is correctly unwrapped."""
    failed_task: asyncio.Future[None] = hass.loop.create_future()
    failed_task.set_exception(ExceptionGroup("tg", [CannotAuthenticate("auth failed")]))
    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: failed_task
    )

    with patch.object(mock_config_entry, "async_start_reauth") as mock_reauth:
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_reauth.assert_called_once_with(hass)


async def test_http2_task_cancelled_exits_early(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cancelled HTTP2 task exits callback early."""
    cancelled_task: asyncio.Future[None] = hass.loop.create_future()
    cancelled_task.cancel()

    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: cancelled_task
    )

    with (
        patch("homeassistant.components.alexa_devices._LOGGER.error") as mock_error,
        patch("homeassistant.components.alexa_devices._LOGGER.warning") as mock_warning,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        patch.object(mock_config_entry, "async_start_reauth") as mock_reauth,
    ):
        await setup_integration(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_error.assert_not_called()
    mock_warning.assert_not_called()
    mock_reload.assert_not_called()
    mock_reauth.assert_not_called()


async def test_http2_task_is_cancelled_on_unload(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HTTP2 task is cancelled during unload."""
    http2_task = hass.loop.create_task(asyncio.sleep(3600))

    mock_amazon_devices_client.start_http2_processing.side_effect = (
        lambda *_args, **_kwargs: http2_task
    )

    await setup_integration(hass, mock_config_entry)

    assert not http2_task.cancelled()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert http2_task.cancelled()
