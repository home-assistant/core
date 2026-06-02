"""Alexa Devices tests configuration."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.alexa_devices.const import (
    CONF_LOGIN_DATA,
    CONF_SITE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    TEST_DEVICE_1,
    TEST_DEVICE_1_SN,
    TEST_PASSWORD,
    TEST_USER_ID,
    TEST_USERNAME,
    TEST_VOCAL_RECORD_INITIAL,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.alexa_devices.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_amazon_devices_client() -> Generator[AsyncMock]:
    """Mock an Alexa Devices client."""
    with (
        patch(
            "homeassistant.components.alexa_devices.coordinator.AmazonEchoApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.alexa_devices.config_flow.AmazonEchoApi",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login = AsyncMock()
        client.login.login_mode_interactive.return_value = {
            "customer_info": {"user_id": TEST_USER_ID},
            CONF_SITE: "https://www.amazon.com",
        }
        client.get_devices_data.return_value = {
            TEST_DEVICE_1_SN: deepcopy(TEST_DEVICE_1)
        }
        client.routines = ["Test Routine"]
        client.sync_history_state = AsyncMock(
            return_value={TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_INITIAL}
        )
        client.on_history_event = MagicMock()
        client.on_volume_state_event = MagicMock()
        client.on_media_state_event = MagicMock()

        async def _start_http2_processing(*_args, **_kwargs) -> asyncio.Task[None]:
            async def _completed_task() -> None:
                return

            return asyncio.create_task(_completed_task())

        client.start_http2_processing = AsyncMock(side_effect=_start_http2_processing)
        client.stop_http2_processing = AsyncMock()
        client.send_sound_notification = AsyncMock()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_LOGIN_DATA: {
                "session": "test-session",
                CONF_SITE: "https://www.amazon.com",
            },
        },
        unique_id=TEST_USER_ID,
        version=1,
        minor_version=3,
    )
