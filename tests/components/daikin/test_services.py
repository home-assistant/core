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

import urllib.parse

import pytest
import voluptuous as vol

from homeassistant.components.daikin import services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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
        self.lztemp_h: dict[int, str] = {}
        self.lztemp_c: dict[int, str] = {}
        self.values = {
            "zone_name": ";".join(z[0] for z in self.zones),
            "zone_onoff": ";".join(z[1] for z in self.zones),
            "lztemp_h": ";".join(
                str(self.lztemp_h.get(i, 22)) for i in range(len(self.zones))
            ),
            "lztemp_c": ";".join(
                str(self.lztemp_c.get(i, 22)) for i in range(len(self.zones))
            ),
        }

    async def set_zone(self, zone_id, param, value) -> None:
        """Simulate setting a zone parameter on the device."""
        self.last_zone_id = zone_id
        self.last_param = param
        self.last_value = value
        if param == "lztemp_h":
            self.lztemp_h[zone_id] = value
        elif param == "lztemp_c":
            self.lztemp_c[zone_id] = value
        # Update values dict to simulate device state
        self.values["lztemp_h"] = ";".join(
            str(self.lztemp_h.get(i, 22)) for i in range(len(self.zones))
        )
        self.values["lztemp_c"] = ";".join(
            str(self.lztemp_c.get(i, 22)) for i in range(len(self.zones))
        )

    async def _get_resource(self, path):
        # Simulate getting or setting zone state
        if path.startswith("aircon/get_zone_setting"):
            return self.values
        # Simulate set_zone_setting: update lztemp_h and lztemp_c dicts from values
        if path.startswith("aircon/set_zone_setting"):
            # Parse params from the path
            parsed = urllib.parse.urlparse(path)
            params = urllib.parse.parse_qs(parsed.query)
            lztemp_h_str = params.get("lztemp_h", [""])[0]
            lztemp_c_str = params.get("lztemp_c", [""])[0]
            lztemp_h_list = (
                urllib.parse.unquote(lztemp_h_str).split(";") if lztemp_h_str else []
            )
            lztemp_c_list = (
                urllib.parse.unquote(lztemp_c_str).split(";") if lztemp_c_str else []
            )
            for i, val in enumerate(lztemp_h_list):
                self.lztemp_h[i] = val
            for i, val in enumerate(lztemp_c_list):
                self.lztemp_c[i] = val
            return True
        return True

    def represent(self, key):
        """Simulate the real device's represent method for lztemp_h and lztemp_c."""
        # Simulate the real device's represent method for lztemp_h and lztemp_c
        if key == "lztemp_h":
            return (None, [self.lztemp_h.get(i, "22") for i in range(len(self.zones))])
        if key == "lztemp_c":
            return (None, [self.lztemp_c.get(i, "22") for i in range(len(self.zones))])
        return (None, [])


class FakeCoordinator:
    """Fake coordinator to simulate the Daikin integration."""

    def __init__(self, device) -> None:
        """Initialize the fake coordinator with a device."""
        self.device = device

    async def async_request_refresh(self) -> None:
        """Simulate coordinator refresh."""


@pytest.fixture
def setup_integration(hass: HomeAssistant):
    """Set up a fake integration with a FakeDevice and FakeCoordinator."""
    device = FakeDevice(
        "00:11:22:33:44:55", target_temperature=22, zones=[["Living", "1", 22]]
    )
    coordinator = FakeCoordinator(device)
    hass.data.setdefault("daikin", {})["test_entry"] = coordinator
    return hass, coordinator


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
    # Check both lztemp_h and lztemp_c are set
    assert device.lztemp_h[0] == "23", (
        f"Expected lztemp_h[0] '23', got {device.lztemp_h.get(0)}"
    )
    assert device.lztemp_c[0] == "23", (
        f"Expected lztemp_c[0] '23', got {device.lztemp_c.get(0)}"
    )


@pytest.mark.asyncio
async def test_service_set_zone_temperature_out_of_range(setup_integration) -> None:
    """Test out-of-range zone temperature service call."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 26}
    with pytest.raises(HomeAssistantError, match="outside the supported range"):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
    # State should not change
    assert coordinator.device.lztemp_h.get(0, 22) == 22
    assert coordinator.device.lztemp_c.get(0, 22) == 22


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
    assert coordinator.device.lztemp_h.get(0, 22) == 22
    assert coordinator2.device.lztemp_h[0] == "21"
    assert coordinator2.device.lztemp_c[0] == "21"


@pytest.mark.asyncio
async def test_service_missing_device(hass: HomeAssistant) -> None:
    """Test service call when device is missing."""

    class NoDeviceCoordinator:
        pass

    hass.data.setdefault("daikin", {})["nodata"] = NoDeviceCoordinator()
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
    for temp in (22, 23, 21):
        service_data = {"zone_id": 0, "temperature": temp}
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
        assert coordinator.device.lztemp_h[0] == str(temp)
        assert coordinator.device.lztemp_c[0] == str(temp)


@pytest.mark.asyncio
async def test_service_unload_services(setup_integration) -> None:
    """Test unloading of Daikin custom services."""
    hass, _ = setup_integration
    await services.async_setup_services(hass)
    await services.async_unload_services(hass)
    # After unloading, the service should not be available
    # Service call is intentionally not executed to avoid ServiceNotFound translations
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
    assert coordinator.device.lztemp_h.get(0) is None


@pytest.mark.asyncio
async def test_service_inactive_zone(setup_integration) -> None:
    """Test service call with an inactive zone."""
    hass, coordinator = setup_integration
    coordinator.device.zones = [["-", "0", 0]]  # Inactive zone
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 22}
    with pytest.raises(HomeAssistantError, match="not active"):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
    assert coordinator.device.lztemp_h.get(0, 22) == 22


@pytest.mark.asyncio
async def test_service_nonexistent_zone(setup_integration) -> None:
    """Test service call with a non-existent zone."""
    hass, coordinator = setup_integration
    await services.async_setup_services(hass)
    service_data = {"zone_id": 99, "temperature": 22}
    with pytest.raises(HomeAssistantError, match="does not exist"):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
    assert coordinator.device.lztemp_h.get(99) is None


@pytest.mark.asyncio
async def test_service_set_zone_temperature_retry(setup_integration) -> None:
    """Test retry mechanism when setting zone temperature fails."""
    hass, coordinator = setup_integration
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
    assert attempt_count == 3
    assert coordinator.device.lztemp_h[0] == "23"
    assert coordinator.device.lztemp_c[0] == "23"


@pytest.mark.asyncio
async def test_service_set_zone_temperature_max_retries_exceeded(
    setup_integration,
) -> None:
    """Test that service fails after maximum retries are exceeded."""
    hass, coordinator = setup_integration

    async def always_fail(*args, **kwargs):
        raise AttributeError("Simulated persistent failure")

    coordinator.device.set_zone = always_fail
    await services.async_setup_services(hass)
    service_data = {"zone_id": 0, "temperature": 23}
    with pytest.raises(HomeAssistantError, match="after 3 attempts"):
        await hass.services.async_call(
            "daikin", services.SERVICE_SET_ZONE_TEMPERATURE, service_data, blocking=True
        )
    assert coordinator.device.lztemp_h.get(0, 22) == 22
