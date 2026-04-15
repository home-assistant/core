"""Test Homee buttons."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from pyHomee.model_homeegram import HomeeGram
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
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


async def setup_mock_button(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_homee: MagicMock
) -> None:
    """Setups a node with buttons for the tests."""
    mock_homee.nodes = [build_mock_node("buttons.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
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


# Homeegram buttons
async def test_homeegram_button_press(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test press homeegram button."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.homeegrams_test_hg_2"},
        blocking=True,
    )

    mock_homee.play_homeegram.assert_called_once_with(3)


async def test_homeegram_button_disabled_by_default(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that homeegram button is disabled by default if it has only one action."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    entry = entity_registry.async_get("button.homeegrams_test_hg_1")
    assert entry is not None
    assert entry.disabled_by == "integration"


async def test_homeegram_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly for homeegram buttons."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is not None

    await mock_homee.add_connection_listener.call_args_list[13][0][0](False)
    await hass.async_block_till_done()

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is STATE_UNAVAILABLE

    await mock_homee.add_connection_listener.call_args_list[13][0][0](True)
    await hass.async_block_till_done()

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is not STATE_UNAVAILABLE


async def test_homeegram_inactive(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if inactive homeegram is sensed correctly for homeegram buttons."""
    await setup_mock_button(hass, mock_config_entry, mock_homee)

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is not None

    # Simulate homeegram becoming inactive
    mock_homee.homeegrams[1].active = False
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is STATE_UNAVAILABLE

    # Simulate homeegram becoming active again
    mock_homee.homeegrams[1].active = True
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("button.homeegrams_test_hg_2")
    assert states.state is not STATE_UNAVAILABLE


@pytest.mark.usefixtures("enable_all_entities")
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
        # Mock actions with AsyncMock for subclasses
        actions_mock = MagicMock()
        actions_mock.data = {
            action_type: [AsyncMock() for _ in action_list]
            for action_type, action_list in hg_data["actions"].items()
        }
        hg_mock.actions = actions_mock
        homeegrams.append(hg_mock)
    return homeegrams
