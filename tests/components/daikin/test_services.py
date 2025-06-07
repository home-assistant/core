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
import voluptuous as vol

from homeassistant.components.daikin import services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound


class FakeDevice:
    """Fake device to simulate the Daikin integration."""

    def __init__(self, mac, target_temperature=22, zones=None) -> None:
        """Initialize the fake device with MAC, target temperature, and zones."""
        self.mac = mac
        self.target_temperature = target_temperature
        self.zones = zones or [["Living", "1", 22]]
        self.last_zone_id: int | None = None
        self.last_param: str | None = None
        self.last_value: str | None = None

    async def set_zone(self, zone_id, param, value) -> None:
        """Simulate setting a zone parameter on the device."""
        self.last_zone_id = zone_id
        self.last_param = param
        self.last_value = value


class FakeCoordinator:
    """Fake coordinator to simulate the Daikin integration."""

    def __init__(self, device) -> None:
        """Initialize the fake coordinator with a device."""
        self.device = device

    async def async_request_refresh(self) -> None:
        """Simulate coordinator refresh."""


@pytest.fixture
async def hass_instance():
    """Return an initialized HomeAssistant instance for testing."""
    hass = HomeAssistant(config_dir="/workspaces/core/config")
    hass.data = {"daikin": {}}
    return hass


@pytest.fixture
def setup_integration(hass_instance):
    """Set up a fake integration with a FakeDevice and FakeCoordinator."""
    device = FakeDevice(
        "00:11:22:33:44:55", target_temperature=22, zones=[["Living", "1", 22]]
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
    assert device.last_zone_id == 0, (
        f"Expected last_zone_id 0, got {device.last_zone_id}"
    )
    assert device.last_param == "lztemp_h", (
        f"Expected last_param 'lztemp_h', got {device.last_param}"
    )
    assert device.last_value == "23", (
        f"Expected last_value '23', got {device.last_value}"
    )


@pytest.mark.asyncio
async def test_service_set_zone_temperature_out_of_range(
    setup_integration, caplog
) -> None:
    """Test out-of-range zone temperature service call."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 26}
    caplog.clear()
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert any("out of range" in m for m in caplog.text.splitlines()), (
        "Expected out of range error log"
    )
    # State should not change
    assert coordinator.device.last_zone_id is None


@pytest.mark.asyncio
async def test_service_entry_filter(setup_integration) -> None:
    """Test filtering of service call based on entry ID."""
    hass, coordinator = setup_integration
    # Add a second coordinator to test filtering
    device2 = FakeDevice(
        "AA:BB:CC:DD:EE:FF", target_temperature=22, zones=[["Office", "1", 22]]
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
    assert coordinator.device.last_zone_id is None, (
        "Expected no update on coordinator.device"
    )
    assert coordinator2.device.last_zone_id == 0, (
        f"Expected last_zone_id 0, got {coordinator2.device.last_zone_id}"
    )
    assert coordinator2.device.last_value == "21", (
        f"Expected last_value '21', got {coordinator2.device.last_value}"
    )


@pytest.mark.asyncio
async def test_service_missing_device(hass_instance: HomeAssistant) -> None:
    """Test service call when device is missing."""
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


@pytest.mark.asyncio
async def test_service_invalid_zone_id_type(setup_integration) -> None:
    """Test service call with invalid zone_id type."""
    hass, _ = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": "not_an_int", "temperature": 22}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )


@pytest.mark.asyncio
async def test_service_invalid_temperature_type(setup_integration) -> None:
    """Test service call with invalid temperature type."""
    hass, _ = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": "not_a_float"}
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )


@pytest.mark.asyncio
async def test_service_multiple_calls(setup_integration) -> None:
    """Test multiple service calls in quick succession."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    for temp in [22, 23, 21]:
        service_data = {"zone_id": 0, "temperature": temp}
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
        assert coordinator.device.last_value == str(temp), (
            f"Expected last_value '{temp}', got {coordinator.device.last_value}"
        )


@pytest.mark.asyncio
async def test_service_unload_services(setup_integration) -> None:
    """Test unloading of Daikin custom services."""
    hass, _ = setup_integration
    await services.async_setup_services(hass)
    await services.async_unload_services(hass)
    # After unloading, the service should not be available
    service_data = {"zone_id": 0, "temperature": 22}
    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
    # Also check that the service is not present in hass.services.async_services()
    assert (
        services.SERVICE_SET_ZONE_TEMPERATURE
        not in hass.services.async_services().get("daikin", {})
    )


@pytest.mark.asyncio
async def test_service_no_zones_support(setup_integration) -> None:
    """Test service call when device doesn't support zones."""
    hass, coordinator = setup_integration
    coordinator.device.zones = None
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 22}
    # The service should log a warning and not raise an exception
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert coordinator.device.last_zone_id is None, (
        "Expected no update when device doesn't support zones"
    )


@pytest.mark.asyncio
async def test_service_inactive_zone(setup_integration, caplog) -> None:
    """Test service call with an inactive zone."""
    hass, coordinator = setup_integration
    coordinator.device.zones = [["-", "0", 0]]  # Inactive zone
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 22}
    caplog.clear()
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert any("not active" in m for m in caplog.text.splitlines()), (
        "Expected not active error log"
    )
    assert coordinator.device.last_zone_id is None


@pytest.mark.asyncio
async def test_service_nonexistent_zone(setup_integration, caplog) -> None:
    """Test service call with a non-existent zone."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 99, "temperature": 22}
    caplog.clear()
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert any("does not exist" in m for m in caplog.text.splitlines()), (
        "Expected does not exist error log"
    )
    assert coordinator.device.last_zone_id is None


@pytest.mark.asyncio
async def test_service_set_zone_temperature_retry(setup_integration) -> None:
    """Test retry mechanism when setting zone temperature fails."""
    hass, coordinator = setup_integration

    # Make the first two attempts fail
    attempt_count = 0
    original_set_zone = coordinator.device.set_zone

    async def failing_set_zone(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise AttributeError("Simulated failure")
        await original_set_zone(*args, **kwargs)

    coordinator.device.set_zone = failing_set_zone

    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 23}
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
    assert coordinator.device.last_value == "23", (
        f"Expected last_value '23', got {coordinator.device.last_value}"
    )


@pytest.mark.asyncio
async def test_service_set_zone_temperature_max_retries_exceeded(
    setup_integration, caplog
) -> None:
    """Test that service fails after maximum retries are exceeded."""
    hass, coordinator = setup_integration

    async def always_fail(*args, **kwargs):
        raise AttributeError("Simulated persistent failure")

    coordinator.device.set_zone = always_fail
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 23}
    caplog.clear()
    await hass.services.async_call(
        "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
    )
    assert any(
        "Failed to set zone temperature after 3 attempts" in m
        for m in caplog.text.splitlines()
    ), "Expected max retries error log"
    assert coordinator.device.last_value is None
