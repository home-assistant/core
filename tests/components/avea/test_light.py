"""Test the Avea light platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_bulb() -> MagicMock:
    """Return a mocked Avea bulb."""
    bulb = MagicMock()
    bulb.name = "Bedroom"
    bulb.brightness = 0
    bulb.connect.return_value = True
    bulb.get_brightness.return_value = 0
    bulb.get_rgb.return_value = (0, 0, 0)
    return bulb


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bulb: MagicMock,
) -> AsyncGenerator[MagicMock]:
    """Set up the integration."""
    with (
        patch(
            "homeassistant.components.avea.async_ble_device_from_address",
            return_value=AVEA_DISCOVERY_INFO.device,
        ),
        patch("homeassistant.components.avea.avea.Bulb", return_value=mock_bulb),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_bulb


async def test_init_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_integration: MagicMock,
) -> None:
    """Test the initial state."""
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.HS]


async def test_turn_on_and_off(
    hass: HomeAssistant,
    setup_integration: MagicMock,
) -> None:
    """Test turning the light on and off."""
    bulb = setup_integration

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(4095)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(2056)

    bulb.set_rgb.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.bedroom", ATTR_HS_COLOR: (0, 100)},
        blocking=True,
    )
    bulb.set_rgb.assert_called_with(255, 0, 0)

    bulb.set_brightness.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: "light.bedroom"},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(0)


async def test_update_state(
    hass: HomeAssistant, setup_integration: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating the entity state."""
    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None

    bulb = setup_integration
    bulb.reset_mock()
    bulb.connect.return_value = True
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (0, 255, 0)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    bulb.connect.assert_called_once()
    bulb.get_brightness.assert_called_once()
    bulb.get_rgb.assert_called_once()
    bulb.disconnect.assert_called_once()

    bulb.assert_has_calls(
        [
            call.connect(),
            call.get_brightness(),
            call.get_rgb(),
            call.disconnect(),
        ]
    )

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_HS_COLOR] == (120.0, 100.0)


async def test_update_state_uses_cached_values_when_connect_fails(
    hass: HomeAssistant, setup_integration: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating the entity state when the shared connection fails."""
    bulb = setup_integration
    bulb.reset_mock()
    bulb.connect.return_value = False
    bulb.get_brightness.return_value = 2048
    bulb.get_rgb.return_value = (0, 255, 0)

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    bulb.connect.assert_called_once()
    bulb.get_brightness.assert_called_once()
    bulb.get_rgb.assert_called_once()
    bulb.disconnect.assert_not_called()

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_HS_COLOR] == (120.0, 100.0)
