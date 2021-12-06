"""Test the update coordinator for HomeWizard Energy."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pytest import raises

from homeassistant.components.homewizard_energy.const import (
    ATTR_ACTIVE_POWER_L1_W,
    ATTR_ACTIVE_POWER_L2_W,
    ATTR_ACTIVE_POWER_L3_W,
    ATTR_ACTIVE_POWER_W,
    ATTR_BRIGHTNESS,
    ATTR_GAS_TIMESTAMP,
    ATTR_METER_MODEL,
    ATTR_POWER_ON,
    ATTR_SMR_VERSION,
    ATTR_SWITCHLOCK,
    ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
    ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
    ATTR_TOTAL_ENERGY_IMPORT_T1_KWH,
    ATTR_TOTAL_ENERGY_IMPORT_T2_KWH,
    ATTR_TOTAL_GAS_M3,
    ATTR_WIFI_SSID,
    ATTR_WIFI_STRENGTH,
    CONF_DATA,
    CONF_DEVICE,
    MODEL_P1,
)
from homeassistant.components.homewizard_energy.coordinator import (
    HWEnergyDeviceUpdateCoordinator as Coordinator,
)
from homeassistant.const import CONF_STATE
from homeassistant.helpers.update_coordinator import UpdateFailed

from .generator import get_mock_device


async def test_coordinator_sets_update_interval(aioclient_mock, hass):
    """Test coordinator calculates correct update interval."""

    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)


async def test_coordinator_fetches_data(aioclient_mock, hass):
    """Test coordinator fetches data."""

    # P1 meter and (very advanced kWh meter)
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 50
    meter.data.available_datapoints = [
        ATTR_ACTIVE_POWER_L1_W,
        ATTR_ACTIVE_POWER_L2_W,
        ATTR_ACTIVE_POWER_L3_W,
        ATTR_ACTIVE_POWER_W,
        ATTR_GAS_TIMESTAMP,
        ATTR_METER_MODEL,
        ATTR_SMR_VERSION,
        ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
        ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
        ATTR_TOTAL_ENERGY_IMPORT_T1_KWH,
        ATTR_TOTAL_ENERGY_IMPORT_T2_KWH,
        ATTR_TOTAL_GAS_M3,
        ATTR_WIFI_SSID,
        ATTR_WIFI_STRENGTH,
    ]

    coordinator = Coordinator(hass, meter)
    data = await coordinator._async_update_data()

    assert data[CONF_DEVICE] == meter.device

    for datapoint in meter.data.available_datapoints:
        assert datapoint in data[CONF_DATA]

    assert data[CONF_STATE] is None

    # Socket
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 50
    meter.data.available_datapoints = [
        ATTR_ACTIVE_POWER_L1_W,
        ATTR_ACTIVE_POWER_L2_W,
        ATTR_ACTIVE_POWER_L3_W,
        ATTR_ACTIVE_POWER_W,
        ATTR_GAS_TIMESTAMP,
        ATTR_METER_MODEL,
        ATTR_SMR_VERSION,
        ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
        ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
        ATTR_TOTAL_ENERGY_IMPORT_T1_KWH,
        ATTR_TOTAL_ENERGY_IMPORT_T2_KWH,
        ATTR_TOTAL_GAS_M3,
        ATTR_WIFI_SSID,
        ATTR_WIFI_STRENGTH,
    ]

    meter.state = AsyncMock()
    meter.state.power_on = False
    meter.state.switch_lock = False
    meter.state.brightness = 255

    coordinator = Coordinator(hass, meter)
    data = await coordinator._async_update_data()

    assert data[CONF_DEVICE] == meter.device

    for datapoint in meter.data.available_datapoints:
        assert datapoint in data[CONF_DATA]

    assert data[CONF_STATE] is not None
    assert data[CONF_STATE][ATTR_POWER_ON] == meter.state.power_on
    assert data[CONF_STATE][ATTR_SWITCHLOCK] == meter.state.switch_lock
    assert data[CONF_STATE][ATTR_BRIGHTNESS] == meter.state.brightness


async def test_coordinator_failed_to_update(aioclient_mock, hass):
    """Test coordinator handles failed update correctly."""

    # Update failed by internal error
    meter = get_mock_device(product_type=MODEL_P1)

    async def _failed_update() -> bool:
        return False

    meter.update = _failed_update

    with raises(UpdateFailed):
        coordinator = Coordinator(hass, meter)
        await coordinator._async_update_data()
