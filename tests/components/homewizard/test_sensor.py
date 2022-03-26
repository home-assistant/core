"""Test the update coordinator for HomeWizard."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohwenergy.errors import DisabledError

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

from .generator import get_mock_device

from tests.common import async_fire_time_changed


async def test_sensor_entity_smr_version(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads smr version."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "smr_version",
    ]
    api.data.smr_version = 50

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

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


async def test_sensor_entity_meter_model(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads meter model."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "meter_model",
    ]
    api.data.meter_model = "Model X"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_smart_meter_model")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_smart_meter_model"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_meter_model"
    assert not entry.disabled
    assert state.state == "Model X"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Smart Meter Model"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"


async def test_sensor_entity_wifi_ssid(hass, mock_config_entry_data, mock_config_entry):
    """Test entity loads wifi ssid."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "wifi_ssid",
    ]
    api.data.wifi_ssid = "My Wifi"

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_wifi_ssid")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_ssid")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_wifi_ssid"
    assert not entry.disabled
    assert state.state == "My Wifi"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Wifi SSID"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:wifi"


async def test_sensor_entity_wifi_strength(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads wifi strength."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "wifi_strength",
    ]
    api.data.wifi_strength = 42

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wifi_strength")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_strength"
    assert entry.disabled


async def test_sensor_entity_total_power_import_t1_kwh(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total power import t1."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_import_t1_kwh",
    ]
    api.data.total_power_import_t1_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_import_t1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_import_t1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_import_t1_kwh"
    assert not entry.disabled
    assert state.state == "1234.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Import T1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_import_t2_kwh(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total power import t2."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_import_t2_kwh",
    ]
    api.data.total_power_import_t2_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_import_t2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_import_t2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_import_t2_kwh"
    assert not entry.disabled
    assert state.state == "1234.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Import T2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t1_kwh(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total power export t1."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_export_t1_kwh",
    ]
    api.data.total_power_export_t1_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_export_t1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_export_t1_kwh"
    assert not entry.disabled
    assert state.state == "1234.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Export T1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t2_kwh(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total power export t2."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_export_t2_kwh",
    ]
    api.data.total_power_export_t2_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_power_export_t2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_power_export_t2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_power_export_t2_kwh"
    assert not entry.disabled
    assert state.state == "1234.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Power Export T2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads active power."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "active_power_w",
    ]
    api.data.active_power_w = 123.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_active_power")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_w"
    assert not entry.disabled
    assert state.state == "123.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l1(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads active power l1."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "active_power_l1_w",
    ]
    api.data.active_power_l1_w = 123.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l1_w"
    assert not entry.disabled
    assert state.state == "123.123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L1"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l2(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads active power l2."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "active_power_l2_w",
    ]
    api.data.active_power_l2_w = 456.456

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l2_w"
    assert not entry.disabled
    assert state.state == "456.456"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L2"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l3(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads active power l3."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "active_power_l3_w",
    ]
    api.data.active_power_l3_w = 789.789

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_power_l3")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l3"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_l3_w"
    assert not entry.disabled
    assert state.state == "789.789"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active Power L3"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_gas(hass, mock_config_entry_data, mock_config_entry):
    """Test entity loads total gas."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_gas_m3",
    ]
    api.data.total_gas_m3 = 50

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_gas")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_total_gas")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_gas_m3"
    assert not entry.disabled
    assert state.state == "50"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total Gas"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_GAS
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_disabled_when_null(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test sensor disables data with null by default."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "active_power_l2_w",
        "active_power_l3_w",
        "total_gas_m3",
    ]
    api.data.active_power_l2_w = None
    api.data.active_power_l3_w = None
    api.data.total_gas_m3 = None

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l2"
    )
    assert entry is None

    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_power_l3"
    )
    assert entry is None

    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_total_gas")
    assert entry is None


async def test_sensor_entity_export_disabled_when_unused(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test sensor disables export if value is 0."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_export_t1_kwh",
        "total_power_export_t2_kwh",
    ]
    api.data.total_power_export_t1_kwh = 0
    api.data.total_power_export_t2_kwh = 0

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
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


async def test_sensors_unreachable(hass, mock_config_entry_data, mock_config_entry):
    """Test sensor handles api unreachable."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_import_t1_kwh",
    ]
    api.data.total_power_import_t1_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        api.update = AsyncMock(return_value=True)

        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        utcnow = dt_util.utcnow()  # Time after the integration is setup

        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.123"
        )

        api.update = AsyncMock(return_value=False)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=5))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "unavailable"
        )

        api.update = AsyncMock(return_value=True)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=10))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.123"
        )


async def test_api_disabled(hass, mock_config_entry_data, mock_config_entry):
    """Test sensor handles api unreachable."""

    api = get_mock_device()
    api.data.available_datapoints = [
        "total_power_import_t1_kwh",
    ]
    api.data.total_power_import_t1_kwh = 1234.123

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=api,
    ):
        api.update = AsyncMock(return_value=True)

        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        utcnow = dt_util.utcnow()  # Time after the integration is setup

        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.123"
        )

        api.update = AsyncMock(side_effect=DisabledError)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=5))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "unavailable"
        )

        api.update = AsyncMock(return_value=True)
        async_fire_time_changed(hass, utcnow + timedelta(seconds=10))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.123"
        )
