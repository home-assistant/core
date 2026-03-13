"""Tests for the UniFi Access button platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api import ApiError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_button_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test button entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_unlock_door(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test pressing the unlock button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.front_door"},
        blocking=True,
    )

    mock_client.unlock_door.assert_awaited_once_with("door-001")


async def test_unlock_door_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test pressing the unlock button raises on API error."""
    mock_client.unlock_door.side_effect = ApiError("unlock failed")

    with pytest.raises(HomeAssistantError, match="Failed to unlock the door"):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.front_door"},
            blocking=True,
        )
