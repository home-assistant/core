"""Test Dynalite switch."""

from dynalite_devices_lib.switch import DynalitePresetSwitchDevice
import pytest

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import State

from .common import (
    ATTR_METHOD,
    ATTR_SERVICE,
    create_entity_from_device,
    create_mock_device,
    run_service_tests,
)

from tests.common import mock_restore_cache


@pytest.fixture
def mock_device():
    """Mock a Dynalite device."""
    return create_mock_device("switch", DynalitePresetSwitchDevice)


async def test_switch_setup(hass, mock_device):
    """Test a successful setup."""
    await create_entity_from_device(hass, mock_device)
    entity_state = hass.states.get("switch.name")
    assert entity_state.attributes[ATTR_FRIENDLY_NAME] == mock_device.name
    await run_service_tests(
        hass,
        mock_device,
        "switch",
        [
            {ATTR_SERVICE: "turn_on", ATTR_METHOD: "async_turn_on"},
            {ATTR_SERVICE: "turn_off", ATTR_METHOD: "async_turn_off"},
        ],
    )


@pytest.mark.parametrize("saved_state, level", [("on", 1), ("off", 0)])
async def test_switch_restore_state(hass, mock_device, saved_state, level):
    """Test restore from cache."""
    mock_restore_cache(
        hass,
        [
            State(
                "switch.name",
                saved_state,
            )
        ],
    )
    await create_entity_from_device(hass, mock_device)
    mock_device.init_level.assert_called_once_with(level)
