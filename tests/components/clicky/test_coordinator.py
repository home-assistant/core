"""Tests for the Clicky coordinator."""

import asyncio
from collections.abc import Generator
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from pyclicky import AuthenticationError, ClickyAPIError, ConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.clicky.const import (
    CONF_SITE_ID,
    CONF_SITEKEY,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .common import _make_report
from .const import TEST_SITE_ID, TEST_SITEKEY


async def _hang(**kwargs: Any) -> None:
    """Simulate a request that never completes."""
    await asyncio.Event().wait()


# (side effect of the API call, config entry state when the first refresh
# fails, translation key of the error, type of its cause)
FAILURES = [
    pytest.param(
        AuthenticationError("Invalid sitekey"),
        ConfigEntryState.SETUP_ERROR,
        "invalid_auth",
        AuthenticationError,
        id="auth_failure",
    ),
    pytest.param(
        ConnectionError("Connection refused"),
        ConfigEntryState.SETUP_RETRY,
        "cannot_connect",
        ConnectionError,
        id="connection_error",
    ),
    pytest.param(
        TimeoutError(),
        ConfigEntryState.SETUP_RETRY,
        "cannot_connect",
        TimeoutError,
        id="request_timeout",
    ),
    pytest.param(
        ClickyAPIError("Unexpected Error"),
        ConfigEntryState.SETUP_RETRY,
        "api_error",
        ClickyAPIError,
        id="api_error",
    ),
]


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a Clicky config entry to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: TEST_SITE_ID,
            CONF_SITEKEY: TEST_SITEKEY,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_visitors_online() -> Generator[AsyncMock]:
    """Mock the Clicky API calls, returning the visitors online mock."""
    with (
        patch(
            "pyclicky.ClickyClient.visitors_online",
            AsyncMock(return_value=_make_report(5)),
        ) as mock_visitors_online,
        patch(
            "pyclicky.ClickyClient.time_total",
            AsyncMock(return_value=_make_report(120)),
        ),
    ):
        yield mock_visitors_online


def _sensor_states(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> set[str]:
    """Return the states of the Clicky sensors."""
    states = set()
    for key in ("visitorsOnline", "timeTotal"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SITE_ID}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        states.add(state.state)
    return states


@pytest.mark.parametrize(
    ("side_effect", "entry_state", "translation_key", "cause"),
    FAILURES,
)
async def test_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_visitors_online: AsyncMock,
    side_effect: Exception,
    entry_state: ConfigEntryState,
    translation_key: str,
    cause: type[Exception],
) -> None:
    """Test that a failing first refresh fails the config entry setup."""
    mock_visitors_online.side_effect = side_effect

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state
    assert not hass.states.async_all("sensor")


async def test_first_refresh_request_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_visitors_online: AsyncMock,
) -> None:
    """Test that a hanging request times out and the setup is retried."""
    mock_visitors_online.side_effect = _hang

    with patch("homeassistant.components.clicky.coordinator.REQUEST_TIMEOUT", 0):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("sensor")


@pytest.mark.parametrize(
    ("side_effect", "entry_state", "translation_key", "cause"),
    FAILURES,
)
async def test_scheduled_refresh_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_visitors_online: AsyncMock,
    side_effect: Exception,
    entry_state: ConfigEntryState,
    translation_key: str,
    cause: type[Exception],
) -> None:
    """Test that a failing scheduled refresh makes the sensors unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _sensor_states(hass, entity_registry) == {"5", "120"}

    mock_visitors_online.side_effect = side_effect

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert _sensor_states(hass, entity_registry) == {STATE_UNAVAILABLE}

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_exception.translation_domain == DOMAIN
    assert coordinator.last_exception.translation_key == translation_key
    assert isinstance(coordinator.last_exception.__cause__, cause)

    if entry_state is ConfigEntryState.SETUP_ERROR:
        # An authentication failure stops polling until the entry is reloaded.
        return

    # The sensors recover once the API responds again.
    mock_visitors_online.side_effect = None

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _sensor_states(hass, entity_registry) == {"5", "120"}


async def test_http_error_hides_sitekey(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that HTTP errors don't leak the sitekey into logged tracebacks."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: TEST_SITE_ID,
            CONF_SITEKEY: TEST_SITEKEY,
        },
    )
    entry.add_to_hass(hass)

    # pyclicky passes the sitekey as a query parameter and does not wrap
    # ClientResponseError, whose string form includes the full request URL.
    http_error = ClientResponseError(
        Mock(
            real_url=(
                "https://api.clicky.com/api/stats/4"
                f"?site_id={TEST_SITE_ID}&sitekey={TEST_SITEKEY}"
            )
        ),
        (),
        status=500,
        message="Internal Server Error",
    )
    assert TEST_SITEKEY in str(http_error)

    with (
        patch(
            "pyclicky.ClickyClient.visitors_online",
            AsyncMock(return_value=_make_report(5)),
        ) as mock_visitors_online,
        patch(
            "pyclicky.ClickyClient.time_total",
            AsyncMock(return_value=_make_report(120)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data
        assert coordinator.last_update_success

        mock_visitors_online.side_effect = http_error
        caplog.set_level(logging.DEBUG)

        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "cannot_connect"
    assert coordinator.last_exception.__cause__ is None
    assert coordinator.last_exception.__suppress_context__
    assert caplog.records
    assert TEST_SITEKEY not in caplog.text
