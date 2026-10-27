"""Tests for the WattWächter sensor platform."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aio_wattwaechter import (
    WattwaechterConnectionError,
    WattwaechterError,
    WattwaechterNotFoundError,
    WattwaechterRateLimitError,
)
from aio_wattwaechter.models import (
    MeterData,
    SystemInfo,
    _parse_meter_data,
    _parse_unix_time,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.wattwaechter.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_METER_DATA,
    MOCK_METER_DATA_GAS,
    MOCK_METER_DATA_MINIMAL,
    MOCK_METER_DATA_WATER,
    MOCK_SYSTEM_INFO_GAS,
    MOCK_SYSTEM_INFO_WATER,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test all sensor entities created from a full OBIS payload."""
    with patch("homeassistant.components.wattwaechter.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_minimal_meter_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only reported OBIS codes create sensors (dynamic)."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def _get_entity_id(obis_code: str) -> str | None:
        return entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
        )

    # Sensors for reported OBIS codes should exist
    assert _get_entity_id("1.8.0") is not None
    assert _get_entity_id("16.7.0") is not None

    # Sensors for unreported OBIS codes should NOT exist
    assert _get_entity_id("2.8.0") is None
    assert _get_entity_id("32.7.0") is None
    assert _get_entity_id("31.7.0") is None


@pytest.mark.parametrize(
    ("obis_code", "device_class", "state_class", "unit"),
    [
        pytest.param(
            "21.7.0",
            SensorDeviceClass.POWER,
            SensorStateClass.MEASUREMENT,
            "W",
            id="mapped_power_unit",
        ),
        pytest.param(
            "12.7.0",
            SensorDeviceClass.VOLTAGE,
            SensorStateClass.MEASUREMENT,
            "V",
            id="mapped_voltage_unit",
        ),
        pytest.param(
            "91.7.0",
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
            "A",
            id="mapped_current_unit",
        ),
        pytest.param(
            "140.7.0",
            SensorDeviceClass.FREQUENCY,
            SensorStateClass.MEASUREMENT,
            "Hz",
            id="mapped_frequency_unit",
        ),
        pytest.param(
            "1.8.3",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            "kWh",
            id="cumulative_energy",
        ),
        pytest.param(
            "5.8.1",
            SensorDeviceClass.REACTIVE_ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            "kvarh",
            id="cumulative_reactive_energy",
        ),
        pytest.param(
            "23.7.0",
            None,
            None,
            "var",
            id="unmapped_unit_no_statistics",
        ),
        pytest.param(
            "94.91.0",
            None,
            None,
            None,
            id="string_value_plain_sensor",
        ),
        pytest.param(
            "96.5.0",
            None,
            None,
            None,
            id="observable_service_register",
        ),
    ],
)
@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_generic_obis_sensor_classification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    obis_code: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
) -> None:
    """Test device/state class inference for OBIS codes without a description."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
    )
    assert entity_id is not None

    attributes = hass.states.get(entity_id).attributes
    assert attributes.get("device_class") == device_class
    assert attributes.get("state_class") == state_class
    assert attributes.get("unit_of_measurement") == unit


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_generic_obis_sensor_name_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a register without a reported name falls back to the OBIS code."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_94.91.1"
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).original_name == "OBIS 94.91.1"


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_no_entities_for_metadata_registers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test metadata registers (serial number, firmware) create no entities."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_96.1.0"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_DEVICE_ID}_0.2.0")
        is None
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, f"{MOCK_DEVICE_ID}_0.0.0")
        is None
    )


@pytest.mark.usefixtures("mock_client")
async def test_generic_obis_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test generic OBIS sensors are disabled by default, curated ones are not."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    generic_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_21.7.0"
    )
    assert generic_id is not None
    assert (
        entity_registry.async_get(generic_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )

    curated_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_15.8.0"
    )
    assert curated_id is not None
    assert entity_registry.async_get(curated_id).disabled_by is None


@pytest.mark.parametrize(
    "error",
    [
        WattwaechterConnectionError("offline"),
        WattwaechterRateLimitError("rate limited"),
        WattwaechterNotFoundError("not found"),
    ],
    ids=["connection", "rate_limit", "not_found"],
)
async def test_system_info_error_is_best_effort(
    hass: HomeAssistant,
    error: WattwaechterError,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a system-info failure keeps meter sensors up; diagnostics go unknown."""
    mock_client.system_info.side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    meter_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_1.8.0"
    )
    assert meter_id is not None
    assert hass.states.get(meter_id).state != STATE_UNAVAILABLE

    ssid_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_ssid"
    )
    assert ssid_id is not None
    assert (
        entity_registry.async_get(ssid_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )

    # Diagnostic sensors are disabled by default; enable and reload for a state.
    entity_registry.async_update_entity(ssid_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ssid_id).state == STATE_UNKNOWN


async def test_sensor_value_unknown_when_obis_stops_reporting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor reports unknown when its OBIS code is no longer reported."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_2.8.0"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state != STATE_UNKNOWN

    # Device stops reporting the export total OBIS code
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("meter_data", "system_info"),
    [
        pytest.param(MOCK_METER_DATA_GAS, MOCK_SYSTEM_INFO_GAS, id="gas"),
        pytest.param(MOCK_METER_DATA_WATER, MOCK_SYSTEM_INFO_WATER, id="water"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gas_water_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    meter_data: MeterData,
    system_info: SystemInfo,
) -> None:
    """Test the sensor entities of a gas and a water meter."""
    mock_client.meter_data.return_value = meter_data
    mock_client.system_info.return_value = system_info

    with patch("homeassistant.components.wattwaechter.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_gas_water_medium_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switching the medium replaces the gas entities with water entities."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_GAS
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def _get_entity_id(obis_code: str) -> str | None:
        return entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
        )

    gas_volume_id = _get_entity_id("7-0:3.0.0")
    assert gas_volume_id is not None
    assert hass.states.get(gas_volume_id).state == "1234.567"
    assert _get_entity_id("7-0:43.0.0") is not None
    assert _get_entity_id("8-0:1.0.0") is None

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "WattWächter Gas"
    assert device.model_id == "ww_gw_mf"

    # The medium is switched to water on the device
    mock_client.meter_data.return_value = MOCK_METER_DATA_WATER
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_WATER
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _get_entity_id("7-0:3.0.0") is None
    assert _get_entity_id("7-0:43.0.0") is None
    assert hass.states.get(gas_volume_id) is None

    water_volume_id = _get_entity_id("8-0:1.0.0")
    assert water_volume_id is not None
    assert hass.states.get(water_volume_id).state == "321.123"
    water_flow_id = _get_entity_id("8-0:2.0.0")
    assert water_flow_id is not None
    assert hass.states.get(water_flow_id).state == "0.06"

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "WattWächter Wasser"

    # Switching back restores the gas entities under their previous entity IDs
    mock_client.meter_data.return_value = MOCK_METER_DATA_GAS
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _get_entity_id("7-0:3.0.0") == gas_volume_id
    assert hass.states.get(gas_volume_id).state == "1234.567"
    assert _get_entity_id("8-0:1.0.0") is None


async def test_gas_water_volume_last_reset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the volume is a total whose last reset is the start of the reading.

    A correction of the reading on the device keeps the start, so the change
    counts as consumption; a meter exchange starts a new cycle.
    """
    mock_client.meter_data.return_value = MOCK_METER_DATA_GAS
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_7-0:3.0.0"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_LAST_RESET] == "2023-11-14T22:13:20+00:00"

    async def _report(volume: float, meter_since: int | None) -> None:
        data = MOCK_METER_DATA_GAS
        assert data.gw is not None
        mock_client.meter_data.return_value = MeterData(
            timestamp=data.timestamp,
            datetime_str=data.datetime_str,
            values={
                **data.values,
                "7-0:3.0.0": replace(data.values["7-0:3.0.0"], value=volume),
            },
            gw=replace(data.gw, meter_since=_parse_unix_time(meter_since)),
        )
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Correction of the reading downwards: same start
    await _report(1230.0, 1700000000)
    state = hass.states.get(entity_id)
    assert state.state == "1230.0"
    assert state.attributes[ATTR_LAST_RESET] == "2023-11-14T22:13:20+00:00"

    # Meter exchange: the new meter starts its own cycle
    await _report(0.5, 1704067200)
    state = hass.states.get(entity_id)
    assert state.state == "0.5"
    assert state.attributes[ATTR_LAST_RESET] == "2024-01-01T00:00:00+00:00"

    # No reading entered yet (or unknown): no last reset
    await _report(0.6, None)
    assert ATTR_LAST_RESET not in hass.states.get(entity_id).attributes


async def test_stale_medium_entities_removed_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities of a previous medium are removed when the entry is set up."""
    stale = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_DEVICE_ID}_7-0:3.0.0",
        config_entry=mock_config_entry,
    )
    mock_client.meter_data.return_value = MOCK_METER_DATA_WATER
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_WATER

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(stale.entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_8-0:1.0.0"
        )
        is not None
    )


async def test_generic_entities_of_previous_medium_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switching the medium also removes generic registers of the old medium."""
    gas_data = await async_load_json_object_fixture(hass, "meter_data_gas.json", DOMAIN)
    gas_data["7-0:1.0.0"] = {"value": 1234.5, "unit": "m³", "name": "Gas volume"}
    mock_client.meter_data.return_value = _parse_meter_data(gas_data)
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = f"{MOCK_DEVICE_ID}_7-0:1.0.0"
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    mock_client.meter_data.return_value = MOCK_METER_DATA_WATER
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_WATER
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_8-0:1.0.0"
    )


async def test_meter_without_gw_block_keeps_all_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a meter reporting gas and water without a gw block keeps both."""
    mock_client.meter_data.return_value = _parse_meter_data(
        {
            "7-0:3.0.0": {"value": 1234.5, "unit": "m³", "name": "Gas"},
            "8-0:1.0.0": {"value": 321.1, "unit": "m³", "name": "Water"},
        }
    )
    removed = async_capture_events(hass, er.EVENT_ENTITY_REGISTRY_UPDATED)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for obis_code in ("7-0:3.0.0", "8-0:1.0.0"):
        assert entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
        )
    assert not [event for event in removed if event.data["action"] == "remove"]


async def test_gw_ignores_codes_of_other_medium(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a gas device creates no entity for a water code it reports."""
    gas_data = await async_load_json_object_fixture(hass, "meter_data_gas.json", DOMAIN)
    gas_data["8-0:1.0.0"] = {"value": 321.1, "unit": "m³", "name": "Water"}
    mock_client.meter_data.return_value = _parse_meter_data(gas_data)
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_7-0:3.0.0"
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_8-0:1.0.0"
        )
        is None
    )


async def test_new_obis_code_adds_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an OBIS code reported after setup creates its entity without reload."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = f"{MOCK_DEVICE_ID}_2.8.0"
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    mock_client.meter_data.return_value = MOCK_METER_DATA
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "1234.567"


@pytest.mark.parametrize(
    ("obis_code", "unit", "device_class", "state_class"),
    [
        pytest.param(
            "7-0:1.0.0",
            "m³",
            SensorDeviceClass.GAS,
            SensorStateClass.TOTAL_INCREASING,
            id="gas_volume",
        ),
        pytest.param(
            "9-0:1.0.0",
            "m³",
            SensorDeviceClass.WATER,
            SensorStateClass.TOTAL_INCREASING,
            id="hot_water_volume",
        ),
        pytest.param(
            "7-0:44.0.0",
            "m³/h",
            SensorDeviceClass.VOLUME_FLOW_RATE,
            SensorStateClass.MEASUREMENT,
            id="flow_rate",
        ),
        pytest.param(
            "1-0:1.8.0",
            "kWh",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            id="full_electricity_code",
        ),
        pytest.param(
            "7-0:3.8.0",
            "kWh",
            None,
            None,
            id="non_electricity_x8y_no_energy",
        ),
        pytest.param(
            "6-0:1.0.0",
            "m³",
            None,
            None,
            id="unknown_medium_volume",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_generic_full_obis_sensor_classification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    obis_code: str,
    unit: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
) -> None:
    """Test device/state class inference for full A-B:C.D.E OBIS codes."""
    mock_client.meter_data.return_value = _parse_meter_data(
        {obis_code: {"value": 12.5, "unit": unit, "name": "Register"}}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
    )
    assert entity_id is not None

    attributes = hass.states.get(entity_id).attributes
    assert attributes.get("device_class") == device_class
    assert attributes.get("state_class") == state_class
    assert attributes.get("unit_of_measurement") == unit
