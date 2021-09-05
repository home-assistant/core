"""Test the update coordinator for HomeWizard Energy."""

from datetime import timedelta

from homeassistant.components.homewizard_energy.const import (
    MODEL_KWH_1,
    MODEL_KWH_3,
    MODEL_P1,
    MODEL_SOCKET,
)
from homeassistant.components.homewizard_energy.coordinator import (
    HWEnergyDeviceUpdateCoordinator as Coordinator,
)

from .generator import get_mock_device


async def test_coordinator_calculates_update_interval(aioclient_mock, hass):
    """Test coordinator calculates correct update interval."""

    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 50

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=1)

    # KWH 1 phase
    meter = get_mock_device(product_type=MODEL_KWH_1)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # KWH 3 phase
    meter = get_mock_device(product_type=MODEL_KWH_3)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Socket
    meter = get_mock_device(product_type=MODEL_SOCKET)

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Missing config data
    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data = None

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)

    # Not an 5.0 meter config data
    # P1 meter
    meter = get_mock_device(product_type=MODEL_P1)
    meter.data.smr_version = 40

    coordinator = Coordinator(hass, meter)
    assert coordinator.update_interval == timedelta(seconds=5)
