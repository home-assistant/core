"""Fixtures for the Dreo integration tests."""

from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Mock device constants - using test-device-id as this is what's expected in tests
MOCK_DEVICE_ID1 = "test-device-id"
MOCK_DEVICE_ID2 = "test-device-id-2"


# Create a mock fan entity that will be directly added to Home Assistant
class MockDreoFan(FanEntity):
    """Mock Dreo Fan entity."""

    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = False
    entity_id = "fan.test_fan"

    def __init__(self, device_id, client) -> None:
        """Initialize the mock fan."""
        self._device_id = device_id
        self._client = client
        self._attr_unique_id = device_id
        self._attr_name = "Test Fan"
        self._attr_percentage = 100
        self._attr_preset_mode = "auto"
        self._attr_oscillating = True
        self._attr_preset_modes = ["sleep", "auto", "normal", "natural"]
        self._attr_speed_count = 4
        self._low_high_range = (1, 6)

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        """Turn on the fan."""
        command_params = {"power_switch": True}

        if percentage is not None and percentage > 0:
            speed = int(percentage / 25)  # Convert percentage to speed level
            command_params["speed"] = speed
        if preset_mode is not None:
            command_params["mode"] = preset_mode

        self._client.update_status(self._device_id, **command_params)

    async def async_turn_off(self, **kwargs):
        """Turn off the fan."""
        self._client.update_status(self._device_id, power_switch=False)

    async def async_set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        self._client.update_status(self._device_id, mode=preset_mode)

    async def async_set_percentage(self, percentage):
        """Set the speed percentage."""
        if percentage <= 0:
            await self.async_turn_off()
        else:
            speed = int(percentage / 25)  # Convert percentage to speed level
            self._client.update_status(self._device_id, speed=speed)

    async def async_oscillate(self, oscillating):
        """Set oscillation."""
        self._client.update_status(self._device_id, oscillate=oscillating)


@pytest.fixture(name="mock_auth_api", autouse=True)
def fixture_mock_auth_api():
    """Set up Auth fixture."""
    with (
        mock.patch("homeassistant.components.dreo.HsCloud") as mock_auth,
        mock.patch("homeassistant.components.dreo.config_flow.HsCloud", new=mock_auth),
    ):
        # login is sync method
        mock_auth.return_value.login = MagicMock()
        yield mock_auth


@pytest.fixture(name="mock_devices_manager_api", autouse=True)
def fixture_mock_devices_manager_api():
    """Set up DreoData fixture."""
    with mock.patch("homeassistant.components.dreo.DreoData") as mock_devices_manager:
        mock_devices_manager.return_value.async_setup = MagicMock()
        mock_devices_manager.return_value.async_update = MagicMock()
        mock_devices_manager.return_value.client = MagicMock()
        mock_devices_manager.return_value.devices = [
            {
                "deviceSn": MOCK_DEVICE_ID1,
                "deviceName": "Test Fan",
                "model": "DR-HTF001S",
                "moduleFirmwareVersion": "1.0.0",
                "mcuFirmwareVersion": "1.0.0",
            }
        ]
        yield mock_devices_manager


@pytest.fixture
def mock_dreo_client():
    """Return a mock Dreo client."""
    client = MagicMock()
    client.login = MagicMock()
    client.get_devices = MagicMock(
        return_value=[
            {
                "deviceSn": MOCK_DEVICE_ID1,
                "deviceName": "Test Fan",
                "model": "DR-HTF001S",
                "moduleFirmwareVersion": "1.0.0",
                "mcuFirmwareVersion": "1.0.0",
            }
        ]
    )
    client.get_status = MagicMock(
        return_value={
            "power_switch": True,
            "connected": True,
            "mode": "auto",
            "speed": 50,
            "oscillate": True,
        }
    )
    client.update_status = MagicMock()
    return client


@pytest.fixture
def mock_dreo_devices():
    """Return a list of mock Dreo devices."""
    return [
        {
            "deviceSn": MOCK_DEVICE_ID1,
            "deviceName": "Test Fan",
            "model": "DR-HTF001S",
            "moduleFirmwareVersion": "1.0.0",
            "mcuFirmwareVersion": "1.0.0",
        }
    ]


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Dreo",
        data={
            CONF_USERNAME: "test@dreo.com",
            CONF_PASSWORD: "password",
        },
        source=SOURCE_USER,
        entry_id="test",
    )


@pytest.fixture
def mock_fan_entity(mock_dreo_client):
    """Create a mock fan entity."""
    return MockDreoFan(MOCK_DEVICE_ID1, mock_dreo_client)


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry,
    mock_dreo_client,
    mock_dreo_devices,
    mock_fan_entity,
    mock_fan_device_data,
):
    """Set up the Dreo integration for testing."""
    mock_config_entry.add_to_hass(hass)

    # Create runtime data
    runtime_data = MagicMock()
    runtime_data.client = mock_dreo_client
    runtime_data.devices = mock_dreo_devices

    # Set runtime_data
    mock_config_entry.runtime_data = runtime_data

    # Patch the async_setup_entry function to add our mock entity directly
    async def mock_async_setup_entry(
        hass: HomeAssistant | None, config_entry, async_add_entities
    ):
        """Set up the Dreo fan platform with our mock entity."""
        async_add_entities([mock_fan_entity])
        return True

    with patch(
        "homeassistant.components.dreo.fan.async_setup_entry",
        side_effect=mock_async_setup_entry,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_fan_device_data():
    """Mock fan device constants."""
    # Create direct module-level patches for the constants
    with (
        mock.patch(
            "homeassistant.components.dreo.fan.DEVICE_TYPE", new={"DR-HTF001S": "fan"}
        ),
        mock.patch(
            "homeassistant.components.dreo.fan.FAN_DEVICE",
            new={
                "type": "fan",
                "config": {
                    "DR-HTF001S": {
                        "speed_range": (1, 4),
                        "preset_modes": ["auto", "normal"],
                    }
                },
            },
        ),
    ):
        yield
