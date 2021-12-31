"""Test the update coordinator for HomeWizard."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock, patch

from aiohwenergy import errors
from pytest import raises

from homeassistant.components.homewizard.const import CONF_DATA, CONF_DEVICE
from homeassistant.components.homewizard.coordinator import (
    HWEnergyDeviceUpdateCoordinator as Coordinator,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .generator import get_mock_device


async def test_coordinator_sets_update_interval(aioclient_mock, hass):
    """Test coordinator calculates correct update interval."""

    # P1 meter
    meter = get_mock_device(product_type="p1_meter")

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)


def mock_request_response(
    status: int, data: str, content_type: str = "application/json"
):
    """Return the default mocked config entry data."""

    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.content_type = content_type

    async def return_json():
        return json.loads(data)

    async def return_text(format: str):
        return data

    mock_response.json = return_json
    mock_response.text = return_text

    return mock_response


async def test_coordinator_fetches_data(aioclient_mock, hass):
    """Test coordinator fetches data."""

    # P1 meter and (very advanced kWh meter)
    meter = get_mock_device(product_type="p1_meter")
    meter.data.smr_version = 50
    meter.data.available_datapoints = [
        "active_power_l1_w",
        "active_power_l2_w",
        "active_power_l3_w",
        "active_power_w",
        "meter_model",
        "smr_version",
        "total_power_export_t1_kwh",
        "total_power_export_t2_kwh",
        "total_power_import_t1_kwh",
        "total_power_import_t2_kwh",
        "total_gas_m3",
        "wifi_ssid",
        "wifi_strength",
    ]

    coordinator = Coordinator(hass, "1.2.3.4")
    coordinator.api = meter
    data = await coordinator._async_update_data()

    print(data[CONF_DEVICE])
    print(meter.device.product_type)
    assert data[CONF_DEVICE] == meter.device
    assert coordinator.api.host == "1.2.3.4"
    assert coordinator.api == meter

    assert (
        len(coordinator.api.initialize.mock_calls) == 0
    )  # Already initialized by 'coordinator.api = meter'
    assert len(coordinator.api.update.mock_calls) == 2  # Init and update
    assert len(coordinator.api.close.mock_calls) == 0

    for datapoint in meter.data.available_datapoints:
        assert datapoint in data[CONF_DATA]


async def test_coordinator_failed_to_update(aioclient_mock, hass):
    """Test coordinator handles failed update correctly."""

    # Update failed by internal error
    meter = get_mock_device(product_type="p1_meter")

    async def _failed_update() -> bool:
        return False

    meter.update = _failed_update

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=meter,
    ):
        coordinator = Coordinator(hass, "1.2.3.4")

    with raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_detected_disabled_api(aioclient_mock, hass):
    """Test coordinator handles disabled api correctly."""

    # Update failed by internal error
    meter = get_mock_device(product_type="p1_meter")

    async def _failed_update() -> bool:
        raise errors.DisabledError()

    meter.update = _failed_update

    with patch(
        "aiohwenergy.HomeWizardEnergy",
        return_value=meter,
    ):
        coordinator = Coordinator(hass, "1.2.3.4")

    with raises(UpdateFailed):
        await coordinator._async_update_data()
