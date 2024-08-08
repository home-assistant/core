"""Test Dynalite switch."""

from unittest.mock import Mock

from dynalite_devices_lib.switch import DynalitePresetSwitchDevice
import pytest

from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

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
    mock_dev = create_mock_device("switch", DynalitePresetSwitchDevice)
    mock_dev.is_on = False

    def mock_init_level(level):
        mock_dev.is_on = level

    type(mock_dev).init_level = Mock(side_effect=mock_init_level)
    return mock_dev


async def test_switch_setup(hass: HomeAssistant, mock_device) -> None:
    """Test a successful setup."""
    await create_entity_from_device(hass, mock_device)
    entity_state = hass.states.get("switch.name")
    assert entity_state.attributes[ATTR_FRIENDLY_NAME] == mock_device.name
    assert entity_state.state == STATE_OFF
    await run_service_tests(
        hass,
        mock_device,
        "switch",
        [
            {ATTR_SERVICE: "turn_on", ATTR_METHOD: "async_turn_on"},
            {ATTR_SERVICE: "turn_off", ATTR_METHOD: "async_turn_off"},
        ],
    )


@pytest.mark.parametrize(("saved_state", "level"), [(STATE_ON, 1), (STATE_OFF, 0)])
async def test_switch_restore_state(
    hass: HomeAssistant, mock_device, saved_state, level
) -> None:
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
    entity_state = hass.states.get("switch.name")
    assert entity_state.state == saved_state
