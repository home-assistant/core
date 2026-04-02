"""Tests for the Firefly III  sensor platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyfirefly.exceptions import (
    FireflyAuthenticationError,
    FireflyConnectionError,
    FireflyTimeoutError,
)
from pyfirefly.models import Budget
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.firefly_iii.const import DOMAIN
from homeassistant.components.firefly_iii.coordinator import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_firefly_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.firefly_iii._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("exception"),
    [
        FireflyAuthenticationError("bad creds"),
        FireflyConnectionError("cannot connect"),
        FireflyTimeoutError("timeout"),
    ],
)
async def test_refresh_exceptions(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable after coordinator refresh failures."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_firefly_client.get_accounts.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.credit_card_account_balance")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_budget_sensor_updates_after_refresh(
    hass: HomeAssistant,
    mock_firefly_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test budget sensor tracks refreshed coordinator budget objects."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.bills_budget")
    assert state is not None
    assert state.state == "123.45"

    updated_budget_data = await async_load_json_array_fixture(
        hass, "budgets.json", DOMAIN
    )
    updated_budget = deepcopy(updated_budget_data[0])
    updated_budget["attributes"]["spent"][0]["sum"] = "999.99"
    mock_firefly_client.get_budgets.return_value = [Budget.from_dict(updated_budget)]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)

    updated_state = hass.states.get("sensor.bills_budget")
    assert updated_state is not None
    assert updated_state.state == "999.99"
