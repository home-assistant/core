"""Test the Home Assistant solarlog sensor module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from solarlog_cli.solarlog_exceptions import (
    SolarLogConnectionError,
    SolarLogUpdateError,
)
from solarlog_cli.solarlog_models import BatteryData, InverterData, SolarlogData
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.solarlog.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_platform


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

    # test no changes (coordinator.py line 176)
    assert hass.states.get("sensor.inverter_1_consumption_year").state == "354.687"

    freezer.tick(delta=timedelta(hours=1))
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

    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.inverter_1_consumption_year") is None
    assert hass.states.get("sensor.inv_1_consumption_year").state == "354.687"
    assert hass.states.get("sensor.inverter_2_consumption_year") is None
    assert hass.states.get("sensor.inverter_3_consumption_year").state == "0.454"


async def test_battery_data_survives_basic_refresh(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry: EntityRegistry,
) -> None:
    """Test battery data is preserved across a basic refresh and updated by a device refresh."""

    async def return_basic_data() -> SolarlogData:
        return SolarlogData.from_dict(
            await async_load_json_object_fixture(hass, "solarlog_data.json", DOMAIN)
        )

    mock_solarlog_connector.update_basic_data.side_effect = return_basic_data

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    basic_coordinator = mock_config_entry.runtime_data.basic_data_coordinator
    initial_data = basic_coordinator.data
    assert initial_data is not None
    assert hass.states.get("sensor.solarlog_charging_power").state == "50.0"
    assert hass.states.get("sensor.solarlog_discharging_power").state == "0.0"
    assert hass.states.get("sensor.solarlog_charge_level").state == "45.0"

    mock_solarlog_connector.update_device_list.return_value = {}
    mock_solarlog_connector.update_inverter_data.return_value = {}
    mock_solarlog_connector.update_battery_data.side_effect = [
        SolarLogUpdateError(),
        BatteryData(
            charge_power=100.0,
            discharge_power=25.0,
            level=80.0,
            voltage=50.0,
        ),
    ]
    freezer.tick(delta=timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert basic_coordinator.data is not initial_data
    assert hass.states.get("sensor.solarlog_charging_power").state == "50.0"
    assert hass.states.get("sensor.solarlog_discharging_power").state == "0.0"
    assert hass.states.get("sensor.solarlog_charge_level").state == "45.0"

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.solarlog_charging_power").state == "100.0"
    assert hass.states.get("sensor.solarlog_discharging_power").state == "25.0"
    assert hass.states.get("sensor.solarlog_charge_level").state == "80.0"


@pytest.mark.usefixtures("mock_solarlog_connector")
async def test_inverter_via_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
) -> None:
    """Test inverter devices are linked to the controller device via via_device_id."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert controller_device is not None

    entity = entity_registry.async_get("sensor.inverter_1_consumption_year")
    assert entity is not None
    assert entity.device_id is not None
    inverter_device = device_registry.async_get(entity.device_id)
    assert inverter_device is not None

    assert inverter_device.via_device_id == controller_device.id


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

    mock_solarlog_connector.update_basic_data.side_effect = exception
    mock_solarlog_connector.update_basic_data.side_effect = exception
    mock_solarlog_connector.update_energy_data.side_effect = exception
    mock_solarlog_connector.update_inverter_data.side_effect = exception

    freezer.tick(delta=timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(delta=timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.solarlog_power_ac").state == STATE_UNAVAILABLE
