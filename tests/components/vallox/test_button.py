"""Tests for Vallox button platform."""

from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import patch_set_filter_change_date

from tests.common import MockConfigEntry


async def test_reset_filter_button_entitity_press(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test reset filter button entity press."""
    # Act
    with patch_set_filter_change_date() as set_filter_change_date:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={ATTR_ENTITY_ID: "button.vallox_reset_filter_change_date"},
        )
        await hass.async_block_till_done()
        set_filter_change_date.assert_called_once()
