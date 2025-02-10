"""Test Schlage select."""

from unittest.mock import Mock

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry


async def test_select(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test the auto-lock time select entity."""
    entity_id = "select.vault_door_auto_lock_time"

    select = hass.states.get(entity_id)
    assert select is not None
    assert select.state == "15"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "30"},
        blocking=True,
    )
    mock_lock.set_auto_lock_time.assert_called_once_with(30)
