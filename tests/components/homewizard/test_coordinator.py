"""Test the update coordinator for HomeWizard Energy."""

from datetime import timedelta
from unittest.mock import patch

from aiohwenergy import errors
from pytest import raises

from homeassistant.components.homewizard.const import (
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
    CONF_DATA,
    CONF_DEVICE,
    MODEL_P1,
)
from homeassistant.components.homewizard.coordinator import (
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

    coordinator = Coordinator(hass, "1.2.3.4")

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=meter,
    ):
        data = await coordinator._async_update_data()

    assert data[CONF_DEVICE] == meter.device
    assert coordinator.host == "1.2.3.4"
    assert coordinator.api == meter

    assert len(coordinator.api.initialize.mock_calls) == 1
    assert len(coordinator.api.update.mock_calls) == 2  # Init and update
    assert len(coordinator.api.close.mock_calls) == 0

    for datapoint in meter.data.available_datapoints:
        assert datapoint in data[CONF_DATA]

    assert data[CONF_STATE] is None


async def test_coordinator_failed_to_update(aioclient_mock, hass):
    """Test coordinator handles failed update correctly."""

    # Update failed by internal error
    meter = get_mock_device(product_type=MODEL_P1)

    async def _failed_update() -> bool:
        return False

    meter.update = _failed_update

    coordinator = Coordinator(hass, "1.2.3.4")

    with raises(UpdateFailed):
        with patch(
            "aiohwenergy.HomeWizardEnergy",
            return_value=meter,
        ):
            await coordinator._async_update_data()

    assert coordinator.api is None


async def test_coordinator_detected_disabled_api(aioclient_mock, hass):
    """Test coordinator handles disabled api correctly."""

    # Update failed by internal error
    meter = get_mock_device(product_type=MODEL_P1)

    async def _failed_update() -> bool:
        raise errors.DisabledError()

    meter.update = _failed_update

    coordinator = Coordinator(hass, "1.2.3.4")

    with raises(UpdateFailed):
        with patch(
            "aiohwenergy.HomeWizardEnergy",
            return_value=meter,
        ):
            await coordinator._async_update_data()

    assert coordinator.api is None
