"""Test the Home Assistant solarlog sensor module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from solarlog_cli.solarlog_exceptions import (
    SolarLogConnectionError,
    SolarLogUpdateError,
)
from solarlog_cli.solarlog_models import InverterData
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
) -> None:
    """Test all entities."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_add_remove_entities(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if entities are added and old are removed."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.inverter_1_consumption_year").state == "354.687"

    # test no changes (coordinator.py line 114)
    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_solarlog_connector.update_device_list.return_value = {
        0: InverterData(name="Inv 1", enabled=True),
        2: InverterData(name="Inverter 3", enabled=True),
    }
    mock_solarlog_connector.update_inverter_data.return_value = {
        0: InverterData(
            name="Inv 1", enabled=True, consumption_year=354687, current_power=5
        ),
        2: InverterData(
            name="Inverter 3", enabled=True, consumption_year=454, current_power=7
        ),
    }
    mock_solarlog_connector.device_name = {0: "Inv 1", 2: "Inverter 3"}.get
    mock_solarlog_connector.device_enabled = {0: True, 2: True}.get

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.inverter_1_consumption_year") is None
    assert hass.states.get("sensor.inv_1_consumption_year").state == "354.687"
    assert hass.states.get("sensor.inverter_2_consumption_year") is None
    assert hass.states.get("sensor.inverter_3_consumption_year").state == "0.454"


@pytest.mark.parametrize(
    "exception",
    [
        SolarLogConnectionError,
        SolarLogUpdateError,
    ],
)
async def test_connection_error(
    hass: HomeAssistant,
    exception: Exception,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    mock_solarlog_connector.update_data.side_effect = exception

    freezer.tick(delta=timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.solarlog_power_ac").state == STATE_UNAVAILABLE
