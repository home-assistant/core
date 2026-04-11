"""Test Homee buttons."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from pyHomee.model_homeegram import HomeeGram
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, load_json_array_fixture, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.fixture
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_button_press(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test press button service."""
    mock_homee.nodes = [build_mock_node("buttons.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_button_impulse_1"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 5, 1)


# Homeegram buttons
def build_homeegrams() -> list[AsyncMock]:
    """Build a list of AsyncMock instances for homeegrams from fixtures."""
    homeegrams_data = load_json_array_fixture("homeegrams.json", "homee")
    homeegrams = []
    for hg_data in homeegrams_data:
        hg_mock = AsyncMock(spec=HomeeGram)
        # Set basic properties
        for key in ("id", "name", "active"):
            setattr(hg_mock, key, hg_data[key])
        # Mock triggers with AsyncMock for subclasses
        triggers_mock = MagicMock()
        for trigger_type, trigger_list in hg_data["triggers"].items():
            setattr(triggers_mock, trigger_type, [AsyncMock() for _ in trigger_list])
        hg_mock.triggers = triggers_mock
        homeegrams.append(hg_mock)
    return homeegrams


@pytest.mark.usefixtures("enable_all_entities")
async def test_button_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    mock_homee.nodes = [build_mock_node("buttons.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
