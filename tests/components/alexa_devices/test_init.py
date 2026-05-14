"""Tests for the Alexa Devices integration."""

import asyncio
from unittest.mock import AsyncMock, patch

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


async def test_http2_reauth_callback_triggers_reauth(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test on_reauth_required callback passed to start_http2_processing triggers reauth."""
    captured_callback = None

    async def capture_callback(_client, on_reauth_required=None) -> asyncio.Task:
        nonlocal captured_callback
        captured_callback = on_reauth_required
        return hass.loop.create_task(asyncio.sleep(3600))

    mock_amazon_devices_client.start_http2_processing.side_effect = capture_callback

    with patch.object(mock_config_entry, "async_start_reauth") as mock_reauth:
        await setup_integration(hass, mock_config_entry)

        assert captured_callback is not None
        await captured_callback()

    mock_reauth.assert_called_once_with(hass)


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
