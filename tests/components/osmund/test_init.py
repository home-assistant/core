"""Test the Osmund setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from osmund import (
    OsmundApiError,
    OsmundAuthError,
    OsmundConnectionError,
    OsmundScopeError,
    OsmundUnavailableError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

PRICE_NOW = "sensor.hjem_electricity_price_now"


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The entry loads and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        pytest.param(
            OsmundAuthError("Unauthorized"),
            ConfigEntryState.SETUP_ERROR,
            id="invalid_auth",
        ),
        pytest.param(
            OsmundUnavailableError("Too many requests", 42),
            ConfigEntryState.SETUP_RETRY,
            id="unavailable",
        ),
        pytest.param(
            OsmundConnectionError("Timeout"),
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
    ],
)
async def test_setup_checks_the_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """A key that no longer works is an error; an API that cannot answer now is a retry."""
    mock_client.me.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state


async def test_setup_needs_the_prices_scope(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """A key that cannot read prices has nothing to show."""
    key = mock_client.me.return_value
    mock_client.me.return_value = type(key)(
        name=key.name, prefix=key.prefix, scopes=frozenset(), expires_at=None
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "call",
    [
        pytest.param("locations", id="locations"),
        pytest.param("prices", id="tomorrows_prices"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(OsmundAuthError("Revoked"), id="invalid_auth"),
        pytest.param(OsmundScopeError("Scope required"), id="missing_scope"),
        pytest.param(OsmundUnavailableError("Too many requests", 42), id="unavailable"),
        pytest.param(OsmundConnectionError("Timeout"), id="cannot_connect"),
        pytest.param(
            OsmundApiError("Internal error", "internal_error", None), id="api_error"
        ),
    ],
)
async def test_an_update_that_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    call: str,
    exception: Exception,
) -> None:
    """A failed update makes the prices unavailable until an update works again."""
    # 12:50 Danish time: the next update also asks for tomorrow's prices.
    freezer.move_to("2026-11-17 11:50:00+00:00")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PRICE_NOW).state != STATE_UNAVAILABLE

    getattr(mock_client, call).side_effect = exception
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(PRICE_NOW).state == STATE_UNAVAILABLE
