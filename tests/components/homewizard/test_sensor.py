"""Test the update coordinator for HomeWizard."""
from datetime import timedelta
import json
from unittest.mock import AsyncMock, patch

import homewizard_energy.models as models

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, load_fixture


async def test_sensor_entity_smr_version(hass, init_integration):
    """Test entity loads smr version."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_dsmr_version")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_dsmr_version")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_smr_version"
    assert not entry.disabled
    assert state.state == "50"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) DSMR Version"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:counter"


async def test_sensor_entity_meter_model(hass, init_integration):
    """Test entity loads meter model."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_smart_meter_model")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_smart_meter_model"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_meter_model"
    assert not entry.disabled
    assert state.state == "ISKRA  2M550T-101"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Smart Meter Model"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"


async def test_sensor_entity_wifi_ssid(hass, init_integration):
    """Test entity loads wifi ssid."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_wifi_ssid")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_ssid")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_wifi_ssid"
    assert not entry.disabled
    assert state.state == "My Wi-Fi"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Wifi SSID"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"


async def test_sensor_entity_wifi_strength(hass, init_integration):
    """Test entity loads wifi strength."""

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_strength")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_strength"
    assert entry.disabled


async def test_sensor_entity_total_power_import_t1_kwh(hass, init_integration):
    """Test entity loads total power import t1."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_import_t1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_import_t1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_import_t1_kwh"
    assert not entry.disabled
    assert state.state == "1234.111"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Import T1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_import_t2_kwh(hass, init_integration):
    """Test entity loads total power import t2."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_import_t2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_import_t2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_import_t2_kwh"
    assert not entry.disabled
    assert state.state == "5678.222"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Import T2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t1_kwh(hass, init_integration):
    """Test entity loads total power export t1."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_export_t1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_export_t1_kwh"
    assert not entry.disabled
    assert state.state == "4321.333"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Export T1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t2_kwh(hass, init_integration):
    """Test entity loads total power export t2."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_export_t2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_export_t2_kwh"
    assert not entry.disabled
    assert state.state == "8765.444"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Export T2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power(hass, init_integration):
    """Test entity loads active power."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_w"
    assert not entry.disabled
    assert state.state == "-123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l1(hass, init_integration):
    """Test entity loads active power l1."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l1_w"
    assert not entry.disabled
    assert state.state == "-123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l2(hass, init_integration):
    """Test entity loads active power l2."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l2_w"
    assert not entry.disabled
    assert state.state == "456"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l3(hass, init_integration):
    """Test entity loads active power l3."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l3")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l3"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l3_w"
    assert not entry.disabled
    assert state.state == "123.456"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L3"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_gas(hass, init_integration):
    """Test entity loads total gas."""

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_gas")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_total_gas")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_gas_m3"
    assert not entry.disabled
    assert state.state == "1122.333"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Gas"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_GAS
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_not_loaded_when_null(
    hass, mock_config_entry, mock_homewizard_energy_minimal
):
    """Test sensor is not loaded when data was null."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy_minimal,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_smr_version")
        is None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_meter_model")
        is None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_ssid")
        is not None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_strength")
        is not None
    )
    assert (
        entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_total_power_import_t1"
        )
        is not None
    )
    assert (
        entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_total_power_import_t2"
        )
        is not None
    )
    assert (
        entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_total_power_export_t1"
        )
        is not None
    )
    assert (
        entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_total_power_export_t2"
        )
        is not None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power")
        is not None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power_l1")
        is not None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power_l2")
        is None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power_l3")
        is None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_total_gas") is None
    )
    assert (
        entity_registry.async_get("sensor.product_name_aabbccddeeff_gas_timestamp")
        is None
    )


async def test_sensor_export_disabled_when_zero(
    hass, mock_config_entry, mock_homewizard_energy_minimal
):
    """Test export sensors are disabled when value is '0'."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy_minimal,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t1"
    )
    assert entry
    assert entry.disabled

    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t2"
    )
    assert entry
    assert entry.disabled


async def test_sensors_unreachable(hass, mock_config_entry, mock_homewizard_energy):
    """Test sensor handles api unreachable."""

    data_model = models.Data.from_dict(json.loads(load_fixture("homewizard/data.json")))

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=mock_homewizard_energy,
    ):

        mock_homewizard_energy.data = AsyncMock(return_value=data_model)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        utcnow = dt_util.utcnow()  # Time after the integration is setup

        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.111"
        )

        mock_homewizard_energy.data = AsyncMock(side_effect=Exception)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=5))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "unavailable"
        )

        mock_homewizard_energy.data = AsyncMock(return_value=data_model)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=10))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.111"
        )
