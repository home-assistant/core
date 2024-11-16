"""Tests for the acaia buttons."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

BUTTONS = (
    "tare",
    "reset_timer",
    "start_stop_timer",
)


async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia buttons."""

    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_presses(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia button presses."""

    await setup_integration(hass, mock_config_entry)

    for button in BUTTONS:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: f"button.lunar_ddeeff_{button}",
            },
            blocking=True,
        )

        function = getattr(mock_scale, button)
        function.assert_called_once()


async def test_buttons_unavailable_on_disconnected_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the acaia buttons are unavailable when the scale is disconnected."""

    await setup_integration(hass, mock_config_entry)

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state.state == STATE_UNKNOWN

    mock_scale.connected = False
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state.state == STATE_UNAVAILABLE
