"""Test the Home Assistant solarlog sensor module."""

from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogUpdateError,
)
from solarlog_cli.solarlog_models import InverterData
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


async def test_firmware_update_updates_device_info(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that firmware updates update the coordinator device info."""
    mock_solarlog_connector.update_firmware_information.return_value = (
        "1.0",
        date(2024, 1, 1),
    )
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.entry_id),
        config_entry_id=mock_config_entry.entry_id,
    )

    assert device is not None
    assert device.sw_version == "1.0"

    mock_solarlog_connector.update_firmware_information.return_value = (
        "2.0",
        date(2025, 1, 1),
    )
    mock_config_entry.runtime_data.basic_data_coordinator._update_counter = 99

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, mock_config_entry.entry_id),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert device is not None
    assert device.sw_version == "2.0"


@pytest.mark.parametrize(
    "exception",
    [SolarLogConnectionError, SolarLogUpdateError],
)
async def test_firmware_read_error_does_not_fail_initial_refresh(
    hass: HomeAssistant,
    exception: type[Exception],
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test firmware read failures do not prevent the initial data refresh."""
    mock_solarlog_connector.update_firmware_information.side_effect = exception

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    coordinator = mock_config_entry.runtime_data.basic_data_coordinator
    assert coordinator.data is not None
    assert coordinator.data.power_ac == 100
    assert coordinator.data.firmware_version is None
    assert coordinator.data.firmware_release_date is None
    assert coordinator._update_counter == 0
    state = hass.states.get("sensor.solarlog_power_ac")
    assert state is not None
    assert state.state == "100.0"


@pytest.mark.parametrize(
    "exception",
    [SolarLogConnectionError, SolarLogUpdateError],
)
async def test_firmware_read_error_retains_previous_firmware_data(
    hass: HomeAssistant,
    exception: type[Exception],
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test firmware read failures retain previously fetched firmware data."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    coordinator = mock_config_entry.runtime_data.basic_data_coordinator

    mock_solarlog_connector.update_firmware_information.side_effect = exception
    updated_data = deepcopy(coordinator.data)
    updated_data.firmware_version = None
    updated_data.firmware_release_date = None
    updated_data.power_ac = 200.0
    mock_solarlog_connector.update_basic_data.return_value = updated_data
    coordinator._update_counter = 99

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.data is not None
    assert coordinator.data.power_ac == 200
    assert coordinator.data.firmware_version == "1.0"
    assert coordinator.data.firmware_release_date == date(2024, 1, 1)
    assert coordinator._update_counter == 0
    state = hass.states.get("sensor.solarlog_power_ac")
    assert state is not None
    assert state.state == "200.0"


@pytest.mark.parametrize(
    ("recovery_method", "exception"),
    [
        ("login", SolarLogConnectionError),
        ("login", SolarLogUpdateError),
        ("test_extended_data_available", SolarLogConnectionError),
        ("test_extended_data_available", SolarLogUpdateError),
    ],
)
async def test_firmware_auth_recovery_transient_error_keeps_basic_data_available(
    hass: HomeAssistant,
    recovery_method: str,
    exception: type[Exception],
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test transient firmware auth recovery errors do not fail basic data refresh."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    coordinator = mock_config_entry.runtime_data.basic_data_coordinator

    mock_solarlog_connector.update_firmware_information.side_effect = (
        SolarLogAuthenticationError
    )
    getattr(mock_solarlog_connector, recovery_method).side_effect = exception
    coordinator._update_counter = 99

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.data is not None
    assert coordinator.data.power_ac == 100
    state = hass.states.get("sensor.solarlog_power_ac")
    assert state is not None
    assert state.state == "100.0"


async def test_firmware_auth_recovery_probe_auth_error_fails_config_entry(
    hass: HomeAssistant,
    mock_solarlog_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth errors from the extended-data probe are reported as auth failures."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    coordinator = mock_config_entry.runtime_data.basic_data_coordinator

    mock_solarlog_connector.update_firmware_information.side_effect = (
        SolarLogAuthenticationError
    )
    mock_solarlog_connector.test_extended_data_available.side_effect = (
        SolarLogAuthenticationError
    )
    coordinator._update_counter = 99

    freezer.tick(delta=timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solarlog_power_ac")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert len(hass.config_entries.flow.async_progress()) == 1


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
