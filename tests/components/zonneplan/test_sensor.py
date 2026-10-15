"""Tests for the Zonneplan sensor platform."""

import dataclasses
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.components.zonneplan import Platform
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ACCOUNT

from tests.common import MockConfigEntry, snapshot_platform

BATTERY_STATE_ENTITY_ID = "sensor.thuisbatterij_battery_state"
INVERTER_STATE_ENTITY_ID = "sensor.thuisbatterij_inverter_state"
EARNED_TODAY_ENTITY_ID = "sensor.thuisbatterij_earned_today"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.parametrize(
    "frozen_time",
    [
        pytest.param("2026-08-29T08:30:00+00:00", id="prices_published"),
        pytest.param("2026-08-30T00:30:00+00:00", id="prices_incoming"),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    frozen_time: str,
) -> None:
    """Test the sensor entities."""
    freezer.move_to(frozen_time)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "missing_market_segments",
    [
        pytest.param({"electricity"}, id="missing_electricity"),
        pytest.param({"gas"}, id="missing_gas"),
        pytest.param({"electricity", "gas"}, id="no_energy_contract"),
    ],
)
async def test_entities_not_created_for_missing_market_segment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    missing_market_segments: set[str],
) -> None:
    """Test no entities are created for a market segment that isn't on the account."""
    mock_zonneplan_client.async_get_account.return_value = dataclasses.replace(
        MOCK_ACCOUNT,
        address_groups=[
            dataclasses.replace(
                address_group,
                connections=[
                    connection
                    for connection in address_group.connections
                    if connection.market_segment not in missing_market_segments
                ],
            )
            for address_group in MOCK_ACCOUNT.address_groups
        ],
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        sorted(
            entity.entity_id
            for entity in er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == snapshot
    )


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.zonneplan_electricity_used_this_month",
        "sensor.zonneplan_electricity_returned_this_month",
        "sensor.zonneplan_electricity_cost_this_month",
        "sensor.zonneplan_gas_used_this_month",
        "sensor.zonneplan_gas_cost_this_month",
    ],
)
async def test_usage_sensor_unknown_until_data_arrives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    entity_id: str,
) -> None:
    """Test usage sensors are unknown while the grid operator hasn't delivered data.

    Pending windows report zero totals, which must not be shown as zero usage.
    """
    for chart in (
        mock_zonneplan_client.async_get_electricity_chart.return_value,
        mock_zonneplan_client.async_get_gas_chart.return_value,
    ):
        assert chart.group is not None
        chart.group.meta["energy_delivered_sum"] = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "battery_state",
    [
        pytest.param(None, id="missing"),
        pytest.param("Standby", id="unknown_value"),
    ],
)
async def test_battery_state_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    battery_state: str | None,
) -> None:
    """Test the battery and inverter states are unknown for a missing or new value."""
    battery = mock_zonneplan_client.async_get_battery.return_value.battery
    assert battery is not None
    battery.contract.meta["battery_state"] = battery_state
    battery.contract.meta["inverter_state"] = battery_state

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in (BATTERY_STATE_ENTITY_ID, INVERTER_STATE_ENTITY_ID):
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNKNOWN


async def test_battery_earned_today_without_measurement_groups(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test earned today has no last reset when the API returns no day window."""
    mock_zonneplan_client.async_get_battery.return_value.measurement_groups = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(EARNED_TODAY_ENTITY_ID))
    assert state.state == "0.5000000"
    assert ATTR_LAST_RESET not in state.attributes
