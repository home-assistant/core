"""Test Dynalite light."""

from unittest.mock import Mock, PropertyMock

from dynalite_devices_lib.light import DynaliteChannelLightDevice
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State

from .common import (
    ATTR_METHOD,
    ATTR_SERVICE,
    create_entity_from_device,
    create_mock_device,
    get_entry_id_from_hass,
    run_service_tests,
)

from tests.common import mock_restore_cache


@pytest.fixture
def mock_device():
    """Mock a Dynalite device."""
    mock_dev = create_mock_device("light", DynaliteChannelLightDevice)
    mock_dev.brightness = 0

    def mock_is_on():
        return mock_dev.brightness != 0

    type(mock_dev).is_on = PropertyMock(side_effect=mock_is_on)

    def mock_init_level(target):
        mock_dev.brightness = target

    type(mock_dev).init_level = Mock(side_effect=mock_init_level)
    return mock_dev


async def test_light_setup(hass: HomeAssistant, mock_device) -> None:
    """Test a successful setup."""
    await create_entity_from_device(hass, mock_device)
    entity_state = hass.states.get("light.name")
    assert entity_state.attributes[ATTR_FRIENDLY_NAME] == mock_device.name
    assert entity_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert entity_state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert entity_state.state == STATE_OFF
    await run_service_tests(
        hass,
        mock_device,
        "light",
        [
            {ATTR_SERVICE: "turn_on", ATTR_METHOD: "async_turn_on"},
            {ATTR_SERVICE: "turn_off", ATTR_METHOD: "async_turn_off"},
        ],
    )


async def test_unload_config_entry(hass: HomeAssistant, mock_device) -> None:
    """Test when a config entry is unloaded from HA."""
    await create_entity_from_device(hass, mock_device)
    assert hass.states.get("light.name")
    entry_id = await get_entry_id_from_hass(hass)
    assert await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.name").state == STATE_UNAVAILABLE


async def test_remove_config_entry(hass: HomeAssistant, mock_device) -> None:
    """Test when a config entry is removed from HA."""
    await create_entity_from_device(hass, mock_device)
    assert hass.states.get("light.name")
    entry_id = await get_entry_id_from_hass(hass)
    assert await hass.config_entries.async_remove(entry_id)
    await hass.async_block_till_done()
    assert not hass.states.get("light.name")


async def test_light_restore_state(hass: HomeAssistant, mock_device) -> None:
    """Test restore from cache."""
    mock_restore_cache(
        hass,
        [State("light.name", STATE_ON, attributes={ATTR_BRIGHTNESS: 77})],
    )
    await create_entity_from_device(hass, mock_device)
    mock_device.init_level.assert_called_once_with(77)
    entity_state = hass.states.get("light.name")
    assert entity_state.state == STATE_ON
    assert entity_state.attributes[ATTR_BRIGHTNESS] == 77
    assert entity_state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS


async def test_light_restore_state_bad_cache(hass: HomeAssistant, mock_device) -> None:
    """Test restore from a cache without the attribute."""
    mock_restore_cache(
        hass,
        [State("light.name", "abc", attributes={"blabla": 77})],
    )
    await create_entity_from_device(hass, mock_device)
    mock_device.init_level.assert_not_called()
    entity_state = hass.states.get("light.name")
    assert entity_state.state == STATE_OFF
