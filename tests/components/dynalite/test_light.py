"""Test Dynalite light."""

from dynalite_devices_lib.light import DynaliteChannelLightDevice
import pytest

from homeassistant.components.light import SUPPORT_BRIGHTNESS

from .common import (
    ATTR_METHOD,
    ATTR_SERVICE,
    create_entity_from_device,
    create_mock_device,
    run_service_tests,
)


@pytest.fixture
def mock_device():
    """Mock a Dynalite device."""
    return create_mock_device("light", DynaliteChannelLightDevice)


async def test_light_setup(hass, mock_device):
    """Test a successful setup."""
    await create_entity_from_device(hass, mock_device)
    entity_state = hass.states.get("light.name")
    assert entity_state.attributes["friendly_name"] == mock_device.name
    assert entity_state.attributes["brightness"] == mock_device.brightness
    assert entity_state.attributes["supported_features"] == SUPPORT_BRIGHTNESS
    await run_service_tests(
        hass,
        mock_device,
        "light",
        [
            {ATTR_SERVICE: "turn_on", ATTR_METHOD: "async_turn_on"},
            {ATTR_SERVICE: "turn_off", ATTR_METHOD: "async_turn_off"},
        ],
    )
