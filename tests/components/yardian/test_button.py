"""Validate Yardian button behavior."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er  # ⬅️ Add this import

from . import setup_integration

from tests.common import MockConfigEntry


@patch("homeassistant.components.yardian.button.REFRESH_DELAY", 0)
async def test_stop_all_button(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,  # ⬅️ Add this fixture
) -> None:
    """Test pressing the stop irrigation button."""
    await setup_integration(hass, mock_config_entry)

    # Dynamically find the exact generated entity ID for the button
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    button_entry = next(entry for entry in entries if entry.domain == Platform.BUTTON)
    entity_id = button_entry.entity_id

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_yardian_client.stop_irrigation.assert_called_once()
