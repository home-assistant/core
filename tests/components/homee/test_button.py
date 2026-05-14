"""Test Homee buttons."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.BUTTON]):
        yield


async def setup_mock_button(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_homee: MagicMock
) -> None:
    """Setups a node with buttons for the tests."""
    mock_homee.nodes = [build_mock_node("buttons.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


async def test_button_press(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test press button service."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_button_impulse_1"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 5, 1)


async def test_button_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
