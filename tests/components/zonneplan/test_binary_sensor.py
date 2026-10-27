"""Tests for the Zonneplan binary sensor platform."""

import dataclasses
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pyzonneplan import ZonneplanConnectionError
from pyzonneplan.const import ContractType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zonneplan import Platform
from homeassistant.components.zonneplan.const import DOMAIN
from homeassistant.components.zonneplan.coordinator import (
    BATTERY_UPDATE_INTERVAL,
    CHARGE_POINT_UPDATE_INTERVAL,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_ACCOUNT

LOW_PRICE_ENTITY_ID = "binary_sensor.zonneplan_electricity_price_low"
GRID_CONGESTION_ENTITY_ID = "binary_sensor.thuisbatterij_grid_congestion"
AUTOMATIC_CHARGING_PAUSED_ENTITY_ID = "binary_sensor.laadpaal_automatic_charging_paused"
CHARGE_POINT_CONTRACT_UUID = "00000000-0000-4000-8000-000000000301"


@pytest.mark.parametrize(
    "frozen_time",
    [
        pytest.param("2026-08-29T08:30:00+00:00", id="in_low_price_block"),
        pytest.param("2026-08-29T17:30:00+00:00", id="outside_low_price_block"),
        pytest.param("2026-08-30T22:30:00+00:00", id="no_prices_today"),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    frozen_time: str,
) -> None:
    """Test the binary sensor entities."""
    freezer.move_to(frozen_time)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_battery_binary_sensor_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the battery binary sensors become unavailable when an update fails."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get(GRID_CONGESTION_ENTITY_ID))
    assert state.state == STATE_ON

    mock_zonneplan_client.async_get_battery.side_effect = ZonneplanConnectionError(
        "boom"
    )
    freezer.tick(BATTERY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(GRID_CONGESTION_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_charge_point_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the charge point gets its own device."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, CHARGE_POINT_CONTRACT_UUID), mock_config_entry.entry_id
        )
    )
    assert device == snapshot


async def test_charge_point_binary_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charge point binary sensors follow updates and errors."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get(AUTOMATIC_CHARGING_PAUSED_ENTITY_ID))
    assert state.state == STATE_OFF

    charge_point = mock_zonneplan_client.async_get_charge_point.return_value
    charge_point.contracts[0].state.dynamic_charging_flex_suppressed = True
    freezer.tick(CHARGE_POINT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(AUTOMATIC_CHARGING_PAUSED_ENTITY_ID))
    assert state.state == STATE_ON

    mock_zonneplan_client.async_get_charge_point.side_effect = ZonneplanConnectionError(
        "boom"
    )
    freezer.tick(CHARGE_POINT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(AUTOMATIC_CHARGING_PAUSED_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_no_charge_point_entities_without_charge_point(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test no charge point entities are created without a charge point contract."""
    mock_zonneplan_client.async_get_account.return_value = dataclasses.replace(
        MOCK_ACCOUNT,
        address_groups=[
            dataclasses.replace(
                address_group,
                connections=[
                    dataclasses.replace(
                        connection,
                        contracts=[
                            contract
                            for contract in connection.contracts
                            if contract.type != ContractType.CHARGE_POINT
                        ],
                    )
                    for connection in address_group.connections
                ],
            )
            for address_group in MOCK_ACCOUNT.address_groups
        ],
    )

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zonneplan.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_zonneplan_client.async_get_charge_point.assert_not_called()
    assert hass.states.get(AUTOMATIC_CHARGING_PAUSED_ENTITY_ID) is None
