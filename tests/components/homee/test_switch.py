"""Test Homee switches."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from pyHomee.model_homeegram import HomeeGram
import pytest
from syrupy.assertion import SnapshotAssertion
from websockets import frames
from websockets.exceptions import ConnectionClosed

from homeassistant.components.homee.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SwitchDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, load_json_array_fixture, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.SWITCH]):
        yield


async def test_switch_state(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the correct state is returned."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_switch_1").state is not STATE_ON
    switch = mock_homee.nodes[0].attributes[2]
    switch.current_value = 1
    switch.add_on_changed_listener.call_args_list[0][0][0](switch)
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_switch_switch_1").state is STATE_ON


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-on service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_switch_1").state is not STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch_switch_1"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 3, 1)


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-off service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_watchdog").state is STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_watchdog"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 5, 0)


async def test_switch_device_class(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if device class gets set correctly."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_switch_1").attributes["device_class"]
        == SwitchDeviceClass.OUTLET
    )
    assert (
        hass.states.get("switch.test_switch_watchdog").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
    )


async def test_switch_no_name(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch gets no name when it is the main feature of the device."""
    mock_homee.nodes = [build_mock_node("switch_single.json")]
    mock_homee.nodes[0].profile = 2002
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_single").attributes["friendly_name"]
        == "Test Switch Single"
    )


async def test_switch_device_class_no_outlet(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if on_off device class gets set correctly if node-profile is not a plug."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.nodes[0].profile = 2002
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_switch_1").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
    )


async def test_send_error(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test failed set_value command."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    mock_homee.set_value.side_effect = ConnectionClosed(
        rcvd=frames.Close(1002, "Protocol Error"), sent=None
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_switch_switch_1"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "connection_closed"


# Homeegram buttons
async def test_homeegram_button_press(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test press homeegram button."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.homeegrams_test_hg_2"},
        blocking=True,
    )

    mock_homee.play_homeegram.assert_awaited_once_with(3)


async def test_homeegram_turn_off_not_supported(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that turning off a homeegram raises an error."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.homeegrams_test_hg_2"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "homeegram_turn_off_not_supported"


async def test_homeegram_button_disabled_by_default(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that homeegram button is disabled by default if it has only one action."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    entry = entity_registry.async_get("switch.homeegrams_test_hg_1")
    assert entry is not None
    assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


async def test_homeegram_connection_listener(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if loss of connection is sensed correctly for homeegram buttons."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state is not None

    await mock_homee.add_connection_listener.call_args_list[6][0][0](False)
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state == STATE_UNAVAILABLE

    await mock_homee.add_connection_listener.call_args_list[6][0][0](True)
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state != STATE_UNAVAILABLE


async def test_homeegram_playing_in_homee(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if homeegram playing in homee is sensed correctly for homeegram buttons."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state is not None

    # Simulate homeegram playing in homee
    mock_homee.homeegrams[1].play = True
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state == STATE_ON

    # Simulate homeegram stopped in homee
    mock_homee.homeegrams[1].play = False
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state != STATE_ON


async def test_homeegram_inactive(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if inactive homeegram is sensed correctly for homeegram buttons."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state is not None

    # Simulate homeegram becoming inactive
    mock_homee.homeegrams[1].active = False
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state == STATE_UNAVAILABLE

    # Simulate homeegram becoming active again
    mock_homee.homeegrams[1].active = True
    mock_homee.homeegrams[1].add_on_changed_listener.call_args_list[0][0][0](
        mock_homee.homeegrams[1]
    )
    await hass.async_block_till_done()

    states = hass.states.get("switch.homeegrams_test_hg_2")
    assert states.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    mock_homee.homeegrams = build_homeegrams()
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def build_homeegrams() -> list[AsyncMock]:
    """Build a list of AsyncMock instances for homeegrams from fixtures."""
    homeegrams_data = load_json_array_fixture("homeegrams.json", "homee")
    homeegrams = []
    for hg_data in homeegrams_data:
        hg_mock = AsyncMock(spec=HomeeGram)
        # Set basic properties
        for key in ("id", "name", "active", "play"):
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
