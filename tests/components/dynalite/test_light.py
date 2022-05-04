"""Test Dynalite light."""
from dynalite_devices_lib.light import DynaliteChannelLightDevice
import pytest

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
)

from .common import (
    ATTR_METHOD,
    ATTR_SERVICE,
    create_entity_from_device,
    create_mock_device,
    get_entry_id_from_hass,
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
    assert entity_state.attributes[ATTR_FRIENDLY_NAME] == mock_device.name
    assert entity_state.attributes["brightness"] == mock_device.brightness
    assert entity_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert entity_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert entity_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    await run_service_tests(
        hass,
        mock_device,
        "light",
        [
            {ATTR_SERVICE: "turn_on", ATTR_METHOD: "async_turn_on"},
            {ATTR_SERVICE: "turn_off", ATTR_METHOD: "async_turn_off"},
        ],
    )


async def test_unload_config_entry(hass, mock_device):
    """Test when a config entry is unloaded from HA."""
    await create_entity_from_device(hass, mock_device)
    assert hass.states.get("light.name")
    entry_id = await get_entry_id_from_hass(hass)
    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.name").state == STATE_UNAVAILABLE


async def test_remove_config_entry(hass, mock_device):
    """Test when a config entry is removed from HA."""
    await create_entity_from_device(hass, mock_device)
    assert hass.states.get("light.name")
    entry_id = await get_entry_id_from_hass(hass)
    assert await hass.config_entries.async_remove(entry_id)
    await hass.async_block_till_done()
    assert not hass.states.get("light.name")
