"""Tests for the Zonneplan sensor platform."""

import dataclasses
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan import Platform
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ACCOUNT

from tests.common import MockConfigEntry, snapshot_platform


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
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.SENSOR],
    ):
        freezer.move_to(frozen_time)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("missing_market_segment", "entity_id"),
    [
        pytest.param(
            "electricity",
            "sensor.zonneplan_current_electricity_price",
            id="missing_electricity",
        ),
        pytest.param("gas", "sensor.zonneplan_gas_price_daily", id="missing_gas"),
        pytest.param(
            "electricity",
            "sensor.zonneplan_electricity_used_this_month",
            id="missing_electricity_usage",
        ),
        pytest.param(
            "gas", "sensor.zonneplan_gas_used_this_month", id="missing_gas_usage"
        ),
    ],
)
async def test_sensor_unknown_for_missing_market_segment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    missing_market_segment: str,
    entity_id: str,
) -> None:
    """Test a sensor is unknown when its market segment isn't on the account."""
    mock_zonneplan_client.async_get_account.return_value = dataclasses.replace(
        MOCK_ACCOUNT,
        address_groups=[
            dataclasses.replace(
                address_group,
                connections=[
                    connection
                    for connection in address_group.connections
                    if connection.market_segment != missing_market_segment
                ],
            )
            for address_group in MOCK_ACCOUNT.address_groups
        ],
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


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
