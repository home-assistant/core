"""Test the Litter-Robot button entity."""

from unittest.mock import MagicMock

from freezegun import freeze_time
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

BUTTON_ENTITY = "button.test_reset_waste_drawer"


async def test_button(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_account: MagicMock
) -> None:
    """Test the creation and values of the Litter-Robot button."""
    await setup_integration(hass, mock_account, BUTTON_DOMAIN)

    state = hass.states.get(BUTTON_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get(BUTTON_ENTITY)
    assert entry
    assert entry.entity_category is EntityCategory.CONFIG

    with freeze_time("2021-11-15 17:37:00", tz_offset=-7):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: BUTTON_ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert mock_account.robots[0].reset_waste_drawer.call_count == 1
    mock_account.robots[0].reset_waste_drawer.assert_called_with()

    state = hass.states.get(BUTTON_ENTITY)
    assert state
    assert state.state == "2021-11-15T10:37:00+00:00"


async def test_button_command_exception(
    hass: HomeAssistant, mock_account_with_side_effects: MagicMock
) -> None:
    """Test that LitterRobotException is wrapped in HomeAssistantError."""
    await setup_integration(hass, mock_account_with_side_effects, BUTTON_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: BUTTON_ENTITY},
            blocking=True,
        )
