"""Test the update coordinator for HomeWizard."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homewizard_energy.errors import DisabledError, RequestError
from homewizard_energy.models import Data

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
    api.data = AsyncMock(return_value=Data.from_dict({"smr_version": 50}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) DSMR version"
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
    api.data = AsyncMock(return_value=Data.from_dict({"meter_model": "Model X"}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Smart meter model"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"


async def test_sensor_entity_wifi_ssid(hass, mock_config_entry_data, mock_config_entry):
    """Test entity loads wifi ssid."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"wifi_ssid": "My Wifi"}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_wi_fi_ssid")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wi_fi_ssid")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_wifi_ssid"
    assert not entry.disabled
    assert state.state == "My Wifi"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Wi-Fi SSID"
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
    api.data = AsyncMock(return_value=Data.from_dict({"wifi_strength": 42}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_wi_fi_strength")
    assert entry
    assert entry.unique_id == "aabbccddeeff_wifi_strength"
    assert entry.disabled


async def test_sensor_entity_total_power_import_t1_kwh(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total power import t1."""

    api = get_mock_device()
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_import_t1_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Total power import T1"
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
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_import_t2_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Total power import T2"
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
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_export_t1_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Total power export T1"
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
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_export_t2_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Total power export T2"
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
    api.data = AsyncMock(return_value=Data.from_dict({"active_power_w": 123.123}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Active power"
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
    api.data = AsyncMock(return_value=Data.from_dict({"active_power_l1_w": 123.123}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Active power L1"
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
    api.data = AsyncMock(return_value=Data.from_dict({"active_power_l2_w": 456.456}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Active power L2"
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
    api.data = AsyncMock(return_value=Data.from_dict({"active_power_l3_w": 789.789}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Active power L3"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_gas(hass, mock_config_entry_data, mock_config_entry):
    """Test entity loads total gas."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"total_gas_m3": 50}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
        == "Product Name (aabbccddeeff) Total gas"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_GAS
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_liters(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads active liters (watermeter)."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_liter_lpm": 12.345}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_water_usage")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_water_usage"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_liter_lpm"
    assert not entry.disabled
    assert state.state == "12.345"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active water usage"
    )

    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "l/min"
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:water"


async def test_sensor_entity_total_liters(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test entity loads total liters (watermeter)."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"total_liter_m3": 1234.567}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.product_name_aabbccddeeff_total_water_usage")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_total_water_usage"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_total_liter_m3"
    assert not entry.disabled
    assert state.state == "1234.567"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Total water usage"
    )

    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"


async def test_sensor_entity_disabled_when_null(
    hass, mock_config_entry_data, mock_config_entry
):
    """Test sensor disables data with null by default."""

    api = get_mock_device()
    api.data = AsyncMock(
        return_value=Data.from_dict(
            {"active_power_l2_w": None, "active_power_l3_w": None, "total_gas_m3": None}
        )
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
    api.data = AsyncMock(
        return_value=Data.from_dict(
            {"total_power_export_t1_kwh": 0, "total_power_export_t2_kwh": 0}
        )
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
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
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_import_t1_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
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

        api.data.side_effect = RequestError
        async_fire_time_changed(hass, utcnow + timedelta(seconds=5))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "unavailable"
        )

        api.data.side_effect = None
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
    api.data = AsyncMock(
        return_value=Data.from_dict({"total_power_import_t1_kwh": 1234.123})
    )

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
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

        api.data.side_effect = DisabledError
        async_fire_time_changed(hass, utcnow + timedelta(seconds=5))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "unavailable"
        )

        api.data.side_effect = None
        async_fire_time_changed(hass, utcnow + timedelta(seconds=10))
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "sensor.product_name_aabbccddeeff_total_power_import_t1"
            ).state
            == "1234.123"
        )
