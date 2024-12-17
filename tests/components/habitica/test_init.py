"""Test the habitica module."""

import datetime
from http import HTTPStatus
import logging
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.habitica.const import (
    ATTR_ARGS,
    ATTR_DATA,
    ATTR_PATH,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    SERVICE_API_CALL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_NAME
from homeassistant.core import Event, HomeAssistant

from .conftest import (
    ERROR_BAD_REQUEST,
    ERROR_NOT_AUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_TOO_MANY_REQUESTS,
)

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_API_CALL_ARGS = {"text": "Use API from Home Assistant", "type": "todo"}
TEST_USER_NAME = "test_user"


@pytest.fixture
def capture_api_call_success(hass: HomeAssistant) -> list[Event]:
    """Capture api_call events."""
    return async_capture_events(hass, EVENT_API_CALL_SUCCESS)


@pytest.mark.usefixtures("habitica")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_service_call(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    capture_api_call_success: list[Event],
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test integration setup, service call and unload."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert len(capture_api_call_success) == 0

    mock_habitica.post(
        "https://habitica.com/api/v3/tasks/user",
        status=HTTPStatus.CREATED,
        json={"data": TEST_API_CALL_ARGS},
    )

    TEST_SERVICE_DATA = {
        ATTR_NAME: "test-user",
        ATTR_PATH: ["tasks", "user", "post"],
        ATTR_ARGS: TEST_API_CALL_ARGS,
    }
    await hass.services.async_call(
        DOMAIN, SERVICE_API_CALL, TEST_SERVICE_DATA, blocking=True
    )

    assert len(capture_api_call_success) == 1
    captured_data = capture_api_call_success[0].data
    captured_data[ATTR_ARGS] = captured_data[ATTR_DATA]
    del captured_data[ATTR_DATA]
    assert captured_data == TEST_SERVICE_DATA


@pytest.mark.parametrize(
    ("exception"),
    [
        ERROR_BAD_REQUEST,
        ERROR_TOO_MANY_REQUESTS,
        ERROR_NOT_AUTHORIZED,
    ],
    ids=["BadRequestError", "TooManyRequestsError", "NotAuthorizedError"],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    habitica.get_user.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test coordinator update failed."""

    habitica.get_tasks.side_effect = ERROR_NOT_FOUND
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_rate_limited(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator when rate limited."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    habitica.get_user.side_effect = ERROR_TOO_MANY_REQUESTS

    with caplog.at_level(logging.DEBUG):
        freezer.tick(datetime.timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert "Rate limit exceeded, will try again later" in caplog.text
