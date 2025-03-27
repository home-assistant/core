"""Define tests for the Daikin services."""

# Insert fake pydaikin modules before any Home Assistant imports
import sys
import types

if "pydaikin" not in sys.modules:
    fake_pydaikin = types.ModuleType("pydaikin")
    fake_daikin_base = types.ModuleType("pydaikin.daikin_base")

    class Appliance:
        """Fake Appliance class for pydaikin."""

    fake_daikin_base.Appliance = Appliance
    fake_pydaikin.daikin_base = fake_daikin_base
    sys.modules["pydaikin"] = fake_pydaikin
    sys.modules["pydaikin.daikin_base"] = fake_daikin_base

if "pydaikin.factory" not in sys.modules:
    fake_factory = types.ModuleType("pydaikin.factory")

    class DaikinFactory:
        """Fake DaikinFactory class for pydaikin."""

    fake_factory.DaikinFactory = DaikinFactory
    sys.modules["pydaikin.factory"] = fake_factory

import pytest

from homeassistant.components.daikin import services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


# Fake Device and coordinator to simulate the Daikin integration
class FakeDevice:
    """Fake device to simulate the Daikin integration."""

    def __init__(self, mac, target_temperature=22, zones=None) -> None:
        """Initialize FakeDevice with a MAC, target temperature, and zones."""
        self.mac = mac
        self.target_temperature = target_temperature
        self.zones = zones or [["Living", None, 22]]
        self.last_zone_id: int | None = None
        self.last_param: str | None = None
        self.last_value: str | None = None

    async def set_zone(self, zone_id, param, value) -> None:
        """Set zone parameters for the fake device."""
        self.last_zone_id = zone_id
        self.last_param = param
        self.last_value = value


class FakeCoordinator:
    """Fake coordinator to simulate the Daikin integration."""

    def __init__(self, device) -> None:
        """Initialize FakeCoordinator with a device."""
        self.device = device


@pytest.fixture
async def hass_instance():
    """Return an initialized HomeAssistant instance for testing."""
    hass = HomeAssistant(config_dir="/workspaces/core/config")
    hass.data = {"daikin": {}}
    return hass


@pytest.fixture
def setup_integration(hass_instance):
    """Set up a fake integration with a FakeDevice and FakeCoordinator."""
    # Create a fake device with one zone and a target temperature (22°C)
    device = FakeDevice(
        "00:11:22:33:44:55", target_temperature=22, zones=[["Living", None, 22]]
    )
    coordinator = FakeCoordinator(device)
    hass_instance.data["daikin"]["test_entry"] = coordinator
    return hass_instance, coordinator


@pytest.mark.asyncio
async def test_service_set_zone_temperature_success(setup_integration) -> None:
    """Test successful zone temperature service call."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 23}
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    device = coordinator.device
    assert device.last_zone_id == 0
    assert device.last_param == "lztemp_h"
    assert device.last_value == "23"


@pytest.mark.asyncio
async def test_service_set_zone_temperature_out_of_range(setup_integration) -> None:
    """Test out-of-range zone temperature service call."""
    hass, _ = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 26}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )


@pytest.mark.asyncio
async def test_service_entry_filter(setup_integration) -> None:
    """Test filtering of service call based on entry ID."""
    hass, coordinator = setup_integration
    # Add a second coordinator to test filtering
    device2 = FakeDevice(
        "AA:BB:CC:DD:EE:FF", target_temperature=22, zones=[["Office", None, 22]]
    )
    coordinator2 = FakeCoordinator(device2)
    hass.data["daikin"]["entry2"] = coordinator2

    await services.async_setup_services(hass)
    # Call service targeting only "entry2"
    service_data = {"zone_id": 0, "temperature": 21, "entry_id": "entry2"}
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    # Verify only device2 was updated and device in "test_entry" remains unchanged
    assert coordinator.device.last_zone_id is None
    assert coordinator2.device.last_zone_id == 0
    assert coordinator2.device.last_value == "21"


@pytest.mark.asyncio
async def test_service_missing_device(hass_instance) -> None:
    """Test service call when device is missing."""
    # Test when coordinator has no device attribute
    hass = hass_instance

    class NoDeviceCoordinator:
        pass

    hass.data["daikin"]["nodata"] = NoDeviceCoordinator()
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 22, "entry_id": "nodata"}
    # The service should simply log a warning and not raise an exception.
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
