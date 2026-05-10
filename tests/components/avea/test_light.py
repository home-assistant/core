"""Test the Avea light platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

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
from homeassistant.helpers.entity_component import async_update_entity

from . import AVEA_DISCOVERY_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bulb() -> MagicMock:
    """Return a mocked Avea bulb."""
    bulb = MagicMock()
    bulb.name = "Unknown"
    bulb.brightness = 0
    bulb.get_brightness.return_value = 0
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
    assert (entity_entry := entity_registry.async_get("light.bedroom"))
    assert entity_entry.unique_id == AVEA_DISCOVERY_INFO.address


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


async def test_update_state(hass: HomeAssistant, setup_integration: MagicMock) -> None:
    """Test updating the entity state."""
    bulb = setup_integration
    bulb.get_brightness.return_value = 2048

    await async_update_entity(hass, "light.bedroom")

    state = hass.states.get("light.bedroom")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
