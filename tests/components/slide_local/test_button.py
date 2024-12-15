"""Tests for the Slide Local button platform."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_platform(hass, mock_config_entry, [Platform.BUTTON])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_pressing_button(
    hass: HomeAssistant,
    mock_slide_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing button."""
    await setup_platform(hass, mock_config_entry, [Platform.BUTTON])

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.slide_bedroom_calibrate",
        },
        blocking=True,
    )
    mock_slide_api.slide_calibrate.assert_called_once()
