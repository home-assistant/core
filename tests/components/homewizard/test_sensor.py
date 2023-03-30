"""Test the update coordinator for HomeWizard."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homewizard_energy.errors import DisabledError, RequestError
from homewizard_energy.models import Data

from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .generator import get_mock_device

from tests.common import async_fire_time_changed


async def test_sensor_entity_smr_version(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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


async def test_sensor_entity_unique_meter_id(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads unique meter id."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"unique_id": "4E47475955"}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_smart_meter_identifier")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_smart_meter_identifier"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_unique_meter_id"
    assert not entry.disabled
    assert state.state == "NGGYU"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Smart meter identifier"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:alphabetical-variant"


async def test_sensor_entity_wifi_ssid(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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


async def test_sensor_entity_active_tariff(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active_tariff."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_tariff": 2}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_tariff")
    entry = entity_registry.async_get("sensor.product_name_aabbccddeeff_active_tariff")
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_tariff"
    assert not entry.disabled
    assert state.state == "2"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active tariff"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:calendar-clock"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert state.attributes.get(ATTR_OPTIONS) == ["1", "2", "3", "4"]


async def test_sensor_entity_wifi_strength(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_import_t2_kwh(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t1_kwh(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_power_export_t2_kwh(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l1(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l2(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_power_l3(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_total_gas(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_unique_gas_meter_id(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads unique gas meter id."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"gas_unique_id": "4E47475955"}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_gas_meter_identifier")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_gas_meter_identifier"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_gas_unique_id"
    assert not entry.disabled
    assert state.state == "NGGYU"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Gas meter identifier"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:alphabetical-variant"


async def test_sensor_entity_active_voltage_l1(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active voltage l1."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_voltage_l1_v": 230.123}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_voltage_l1"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_voltage_l1_v"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_voltage_l1")
        assert state
        assert state.state == "230.123"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active voltage L1"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricPotential.VOLT
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_voltage_l2(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active voltage l2."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_voltage_l2_v": 230.123}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_voltage_l2"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_voltage_l2_v"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_voltage_l2")
        assert state
        assert state.state == "230.123"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active voltage L2"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricPotential.VOLT
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_voltage_l3(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active voltage l3."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_voltage_l3_v": 230.123}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_voltage_l3"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_voltage_l3_v"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_voltage_l3")
        assert state
        assert state.state == "230.123"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active voltage L3"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricPotential.VOLT
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_current_l1(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active current l1."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_current_l1_a": 12.34}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_current_l1"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_current_l1_a"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_current_l1")
        assert state
        assert state.state == "12.34"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active current L1"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricCurrent.AMPERE
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_current_l2(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active current l2."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_current_l2_a": 12.34}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_current_l2"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_current_l2_a"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_current_l2")
        assert state
        assert state.state == "12.34"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active current L2"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricCurrent.AMPERE
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_current_l3(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active current l3."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_current_l3_a": 12.34}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_current_l3"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_current_l3_a"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_current_l3")
        assert state
        assert state.state == "12.34"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active current L3"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == UnitOfElectricCurrent.AMPERE
        )
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_frequency(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active frequency."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"active_frequency_hz": 50.12}))

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

        disabled_entry = entity_registry.async_get(
            "sensor.product_name_aabbccddeeff_active_frequency"
        )
        assert disabled_entry
        assert disabled_entry.disabled
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Enable
        entry = entity_registry.async_update_entity(
            disabled_entry.entity_id, **{"disabled_by": None}
        )
        await hass.async_block_till_done()
        assert not entry.disabled
        assert entry.unique_id == "aabbccddeeff_active_frequency_hz"

        # Let HA reload the integration so state is set
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=30),
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.product_name_aabbccddeeff_active_frequency")
        assert state
        assert state.state == "50.12"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "Product Name (aabbccddeeff) Active frequency"
        )
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfFrequency.HERTZ
        assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.FREQUENCY
        assert ATTR_ICON not in state.attributes


async def test_sensor_entity_voltage_sag_count_l1(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_sag_count_l1."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_sag_l1_count": 123}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_voltage_sags_detected_l1")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_sags_detected_l1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_sag_l1_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage sags detected L1"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_voltage_sag_count_l2(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_sag_count_l2."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_sag_l2_count": 123}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_voltage_sags_detected_l2")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_sags_detected_l2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_sag_l2_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage sags detected L2"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_voltage_sag_count_l3(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_sag_count_l3."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_sag_l3_count": 123}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_voltage_sags_detected_l3")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_sags_detected_l3"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_sag_l3_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage sags detected L3"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_voltage_swell_count_l1(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_swell_count_l1."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_swell_l1_count": 123}))

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

    state = hass.states.get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l1"
    )
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l1"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_swell_l1_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage swells detected L1"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_voltage_swell_count_l2(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_swell_count_l2."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_swell_l2_count": 123}))

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

    state = hass.states.get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l2"
    )
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l2"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_swell_l2_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage swells detected L2"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_voltage_swell_count_l3(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads voltage_swell_count_l3."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"voltage_swell_l3_count": 123}))

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

    state = hass.states.get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l3"
    )
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_voltage_swells_detected_l3"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_voltage_swell_l3_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Voltage swells detected L3"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_any_power_fail_count(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads any power fail count."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"any_power_fail_count": 123}))

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

    state = hass.states.get("sensor.product_name_aabbccddeeff_power_failures_detected")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_power_failures_detected"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_any_power_fail_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Power failures detected"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_long_power_fail_count(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads long power fail count."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"long_power_fail_count": 123}))

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

    state = hass.states.get(
        "sensor.product_name_aabbccddeeff_long_power_failures_detected"
    )
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_long_power_failures_detected"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_long_power_fail_count"
    assert not entry.disabled
    assert state.state == "123"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Long power failures detected"
    )
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_sensor_entity_active_power_average(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads active power average."""

    api = get_mock_device()
    api.data = AsyncMock(
        return_value=Data.from_dict({"active_power_average_w": 123.456})
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

    state = hass.states.get("sensor.product_name_aabbccddeeff_active_average_demand")
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_active_average_demand"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_active_power_average_w"
    assert not entry.disabled
    assert state.state == "123.456"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Active average demand"
    )

    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_monthly_power_peak(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity loads monthly power peak."""

    api = get_mock_device()
    api.data = AsyncMock(return_value=Data.from_dict({"montly_power_peak_w": 1234.456}))

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

    state = hass.states.get(
        "sensor.product_name_aabbccddeeff_peak_demand_current_month"
    )
    entry = entity_registry.async_get(
        "sensor.product_name_aabbccddeeff_peak_demand_current_month"
    )
    assert entry
    assert state
    assert entry.unique_id == "aabbccddeeff_monthly_power_peak_w"
    assert not entry.disabled
    assert state.state == "1234.456"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Peak demand current month"
    )

    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert ATTR_ICON not in state.attributes


async def test_sensor_entity_active_liters(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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

    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "l/min"
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes.get(ATTR_ICON) == "mdi:water"


async def test_sensor_entity_total_liters(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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

    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    assert state.attributes.get(ATTR_ICON) == "mdi:gauge"


async def test_sensor_entity_disabled_when_null(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test sensor disables export if value is 0."""

    api = get_mock_device()
    api.data = AsyncMock(
        return_value=Data.from_dict(
            {
                "total_power_export_kwh": 0,
                "total_power_export_t1_kwh": 0,
                "total_power_export_t2_kwh": 0,
                "total_power_export_t3_kwh": 0,
                "total_power_export_t4_kwh": 0,
            }
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
        "sensor.product_name_aabbccddeeff_total_power_export"
    )
    assert entry
    assert entry.disabled

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


async def test_sensors_unreachable(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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


async def test_api_disabled(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
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
