"""Tests for Fritz!Tools button platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.fritz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_button_setup(hass: HomeAssistant, fc_class_mock, fh_class_mock):
    """Test setup of Fritz!Tools buttons."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    buttons = hass.states.async_all(BUTTON_DOMAIN)
    assert len(buttons) == 4

    for button in buttons:
        assert button.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "entity_id, wrapper_method",
    [
        ("button.mock_title_firmware_update", "async_trigger_firmware_update"),
        ("button.mock_title_reboot", "async_trigger_reboot"),
        ("button.mock_title_reconnect", "async_trigger_reconnect"),
        ("button.mock_title_cleanup", "async_trigger_cleanup"),
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    entity_id: str,
    wrapper_method: str,
    fc_class_mock,
    fh_class_mock,
):
    """Test Fritz!Tools buttons."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    button = hass.states.get(entity_id)
    assert button
    assert button.state == STATE_UNKNOWN
    with patch(
        f"homeassistant.components.fritz.common.AvmWrapper.{wrapper_method}"
    ) as mock_press_action:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_press_action.assert_called_once()

        button = hass.states.get(entity_id)
        assert button.state != STATE_UNKNOWN
