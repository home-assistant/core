"""Tests for Miele button module."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = Platform.BUTTON
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "button.washing_machine_start"


async def test_button_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test button entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_press(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test button press."""

    await hass.services.async_call(
        TEST_PLATFORM, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    mock_miele_client.send_action.assert_called_once_with(
        "Dummy_Appliance_3", {"processAction": 1}
    )


async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientResponseError("test", "Test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    mock_miele_client.send_action.assert_called_once()
