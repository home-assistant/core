import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


# Fake Device and coordinator to simulate the Daikin integration
class FakeDevice:
    def __init__(self, mac, target_temperature=22, zones=None):
        self.mac = mac
        self.target_temperature = target_temperature
        self.zones = zones or [["Living", None, 22]]
    async def set_zone(self, zone_id, param, value):
        self.last_zone_id = zone_id
        self.last_param = param
        self.last_value = value

class FakeCoordinator:
    def __init__(self, device):
        self.device = device

@pytest.fixture
def hass_instance(event_loop):
    hass = HomeAssistant()
    hass.loop = event_loop
    hass.data = {"daikin": {}}
    return hass

@pytest.fixture
def setup_integration(hass_instance):
    # Create a fake device with one zone and a target temperature (22°C)
    device = FakeDevice("00:11:22:33:44:55", target_temperature=22, zones=[["Living", None, 22]])
    coordinator = FakeCoordinator(device)
    hass_instance.data["daikin"]["test_entry"] = coordinator
    return hass_instance, coordinator

@pytest.mark.asyncio
async def test_service_set_zone_temperature_success(setup_integration):
    hass, coordinator = setup_integration
    from homeassistant.components.daikin.services import (
        SERVICE_SET_ZONE_TEMPERATURE,
        async_setup_services,
    )

    await async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 23}
    await hass.services.async_call("daikin", SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True)
    device = coordinator.device
    assert device.last_zone_id == 0
    assert device.last_param == "lztemp_h"
    assert device.last_value == "23"

@pytest.mark.asyncio
async def test_service_set_zone_temperature_out_of_range(setup_integration):
    hass, _ = setup_integration
    from homeassistant.components.daikin.services import (
        SERVICE_SET_ZONE_TEMPERATURE,
        async_setup_services,
    )
    await async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 26}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("daikin", SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True)

@pytest.mark.asyncio
async def test_service_entry_filter(setup_integration):
    hass, coordinator = setup_integration
    from homeassistant.components.daikin.services import (
        SERVICE_SET_ZONE_TEMPERATURE,
        async_setup_services,
    )
    # Add a second coordinator to test filtering
    device2 = FakeDevice("AA:BB:CC:DD:EE:FF", target_temperature=22, zones=[["Office", None, 22]])
    coordinator2 = FakeCoordinator(device2)
    hass.data["daikin"]["entry2"] = coordinator2

    await async_setup_services(hass)
    # Call service targeting only "entry2"
    service_data = {"zone_id": 0, "temperature": 21, "entry_id": "entry2"}
    await hass.services.async_call("daikin", SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True)
    # Verify only device2 was updated and device in "test_entry" remains unchanged
    assert not hasattr(coordinator.device, "last_zone_id")
    assert coordinator2.device.last_zone_id == 0
    assert coordinator2.device.last_value == "21"

@pytest.mark.asyncio
async def test_service_missing_device(hass_instance):
    # Test when coordinator has no device attribute
    hass = hass_instance
    class NoDeviceCoordinator:
        pass
    hass.data["daikin"]["nodata"] = NoDeviceCoordinator()
    from homeassistant.components.daikin.services import (
        SERVICE_SET_ZONE_TEMPERATURE,
        async_setup_services,
    )
    await async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 22, "entry_id": "nodata"}
    # The service should simply log a warning and not raise an exception.
    await hass.services.async_call("daikin", SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True)
