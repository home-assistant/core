"""The tests for the Remote component, adapted from Light Test."""

from pytest_homeassistant.common import (
    async_mock_service,
    setup_test_component_platform,
)

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_COMMAND_TYPE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DOMAIN,
    RemoteEntity,
    RemoteEntityFeature,
    RemoteNavigation,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

TEST_PLATFORM = {DOMAIN: {CONF_PLATFORM: "test"}}
SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_DELETE_COMMAND = "delete_command"
ENTITY_ID = "entity_id_val"


async def test_is_on(hass: HomeAssistant) -> None:
    """Test is_on."""
    hass.states.async_set("remote.test", STATE_ON)
    assert remote.is_on(hass, "remote.test")

    hass.states.async_set("remote.test", STATE_OFF)
    assert not remote.is_on(hass, "remote.test")


async def test_turn_on(hass: HomeAssistant) -> None:
    """Test turn_on."""
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID})

    await hass.async_block_till_done()

    assert len(turn_on_calls) == 1
    call = turn_on_calls[-1]

    assert call.domain == DOMAIN


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turn_off."""
    turn_off_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}
    )

    await hass.async_block_till_done()

    assert len(turn_off_calls) == 1
    call = turn_off_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_send_command(hass: HomeAssistant) -> None:
    """Test send_command."""
    send_command_calls = async_mock_service(hass, DOMAIN, SERVICE_SEND_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
        ATTR_NUM_REPEATS: "4",
        ATTR_DELAY_SECS: "0.6",
    }

    await hass.services.async_call(DOMAIN, SERVICE_SEND_COMMAND, data)

    await hass.async_block_till_done()

    assert len(send_command_calls) == 1
    call = send_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_SEND_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


async def test_learn_command(hass: HomeAssistant) -> None:
    """Test learn_command."""
    learn_command_calls = async_mock_service(hass, DOMAIN, SERVICE_LEARN_COMMAND)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
        ATTR_COMMAND_TYPE: "rf",
        ATTR_ALTERNATIVE: True,
        ATTR_TIMEOUT: 20,
    }
    await hass.services.async_call(DOMAIN, SERVICE_LEARN_COMMAND, data)

    await hass.async_block_till_done()

    assert len(learn_command_calls) == 1
    call = learn_command_calls[-1]

    assert call.domain == DOMAIN
    assert call.service == SERVICE_LEARN_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID


class NavigationRemote(RemoteEntity):
    """Remote that supports navigation through the synchronous method only."""

    _attr_name = "Navigation"
    _attr_supported_features = RemoteEntityFeature.NAVIGATE

    def __init__(self) -> None:
        """Initialize the remote."""
        self.navigated: list[RemoteNavigation] = []

    def navigate(self, direction: RemoteNavigation) -> None:
        """Record the navigation action."""
        self.navigated.append(direction)


async def test_navigate_default_list_and_sync_implementation(
    hass: HomeAssistant,
) -> None:
    """Test navigation defaults to all directions and runs a sync implementation."""
    entity = NavigationRemote()
    setup_test_component_platform(hass, DOMAIN, [entity])
    assert await async_setup_component(hass, DOMAIN, TEST_PLATFORM)
    await hass.async_block_till_done()

    state = hass.states.get("remote.navigation")
    assert state is not None
    assert state.attributes["supported_navigation"] == list(RemoteNavigation)

    await hass.services.async_call(
        DOMAIN,
        "navigate",
        {ATTR_ENTITY_ID: "remote.navigation", "direction": "menu"},
        blocking=True,
    )
    assert entity.navigated == [RemoteNavigation.MENU]


async def test_navigate_not_exposed_without_feature(hass: HomeAssistant) -> None:
    """Test the supported navigation list is only exposed with the feature."""
    entity = NavigationRemote()
    entity._attr_supported_features = RemoteEntityFeature(0)
    setup_test_component_platform(hass, DOMAIN, [entity])
    assert await async_setup_component(hass, DOMAIN, TEST_PLATFORM)
    await hass.async_block_till_done()

    state = hass.states.get("remote.navigation")
    assert state is not None
    assert "supported_navigation" not in state.attributes


async def test_delete_command(hass: HomeAssistant) -> None:
    """Test delete_command."""
    delete_command_calls = async_mock_service(
        hass, remote.DOMAIN, SERVICE_DELETE_COMMAND
    )

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_DEVICE: "test_device",
        ATTR_COMMAND: ["test_command"],
    }

    await hass.services.async_call(DOMAIN, SERVICE_DELETE_COMMAND, data)

    await hass.async_block_till_done()

    assert len(delete_command_calls) == 1
    call = delete_command_calls[-1]

    assert call.domain == remote.DOMAIN
    assert call.service == SERVICE_DELETE_COMMAND
    assert call.data[ATTR_ENTITY_ID] == ENTITY_ID
