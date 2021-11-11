"""The tests for Cover device actions."""
import pytest

import homeassistant.components.automation as automation
from homeassistant.components.cover import (
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_get_device_automation_capabilities,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.mark.parametrize(
    "set_state,features_reg,features_state,expected_action_types",
    [
        (False, 0, 0, []),
        (False, SUPPORT_CLOSE_TILT, 0, ["close_tilt"]),
        (False, SUPPORT_CLOSE, 0, ["close"]),
        (False, SUPPORT_OPEN_TILT, 0, ["open_tilt"]),
        (False, SUPPORT_OPEN, 0, ["open"]),
        (False, SUPPORT_SET_POSITION, 0, ["set_position"]),
        (False, SUPPORT_SET_TILT_POSITION, 0, ["set_tilt_position"]),
        (False, SUPPORT_STOP, 0, ["stop"]),
        (True, 0, 0, []),
        (True, 0, SUPPORT_CLOSE_TILT, ["close_tilt"]),
        (True, 0, SUPPORT_CLOSE, ["close"]),
        (True, 0, SUPPORT_OPEN_TILT, ["open_tilt"]),
        (True, 0, SUPPORT_OPEN, ["open"]),
        (True, 0, SUPPORT_SET_POSITION, ["set_position"]),
        (True, 0, SUPPORT_SET_TILT_POSITION, ["set_tilt_position"]),
        (True, 0, SUPPORT_STOP, ["stop"]),
    ],
)
async def test_get_actions(
    hass,
    device_reg,
    entity_reg,
    set_state,
    features_reg,
    features_state,
    expected_action_types,
):
    """Test we get the expected actions from a cover."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN,
        "test",
        "5678",
        device_id=device_entry.id,
        supported_features=features_reg,
    )
    if set_state:
        hass.states.async_set(
            f"{DOMAIN}.test_5678", "attributes", {"supported_features": features_state}
        )
    await hass.async_block_till_done()

    expected_actions = []
    expected_actions += [
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
        }
        for action in expected_action_types
    ]
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert_lists_same(actions, expected_actions)


async def test_get_action_capabilities(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockCover(
            name="Set position cover",
            is_on=True,
            unique_id="unique_set_pos_cover",
            current_cover_position=50,
            supported_features=SUPPORT_OPEN
            | SUPPORT_CLOSE
            | SUPPORT_STOP
            | SUPPORT_OPEN_TILT
            | SUPPORT_CLOSE_TILT
            | SUPPORT_STOP_TILT,
        ),
    )
    ent = platform.ENTITIES[0]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 5  # open, close, open_tilt, close_tilt
    action_types = {action["type"] for action in actions}
    assert action_types == {"open", "close", "stop", "open_tilt", "close_tilt"}
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        assert capabilities == {"extra_fields": []}


async def test_get_action_capabilities_set_pos(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "position",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            }
        ]
    }
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 1  # set_position
    action_types = {action["type"] for action in actions}
    assert action_types == {"set_position"}
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        if action["type"] == "set_position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {"extra_fields": []}


async def test_get_action_capabilities_set_tilt_pos(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover action."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[3]

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "position",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            }
        ]
    }
    actions = await async_get_device_automations(hass, "action", device_entry.id)
    assert len(actions) == 3
    action_types = {action["type"] for action in actions}
    assert action_types == {"open", "close", "set_tilt_position"}
    for action in actions:
        capabilities = await async_get_device_automation_capabilities(
            hass, "action", action
        )
        if action["type"] == "set_tilt_position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {"extra_fields": []}


async def test_action(hass, enable_custom_integrations):
    """Test for cover actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event_open"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "open",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_close"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "close",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_stop"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "stop",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    open_calls = async_mock_service(hass, "cover", "open_cover")
    close_calls = async_mock_service(hass, "cover", "close_cover")
    stop_calls = async_mock_service(hass, "cover", "stop_cover")

    hass.bus.async_fire("test_event_open")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 0
    assert len(stop_calls) == 0

    hass.bus.async_fire("test_event_close")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1
    assert len(stop_calls) == 0

    hass.bus.async_fire("test_event_stop")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1
    assert len(stop_calls) == 1


async def test_action_tilt(hass, enable_custom_integrations):
    """Test for cover tilt actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event_open"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "open_tilt",
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event_close"},
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "close_tilt",
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    open_calls = async_mock_service(hass, "cover", "open_cover_tilt")
    close_calls = async_mock_service(hass, "cover", "close_cover_tilt")

    hass.bus.async_fire("test_event_open")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 0

    hass.bus.async_fire("test_event_close")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1

    hass.bus.async_fire("test_event_stop")
    await hass.async_block_till_done()
    assert len(open_calls) == 1
    assert len(close_calls) == 1


async def test_action_set_position(hass, enable_custom_integrations):
    """Test for cover set position actions."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_pos",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "set_position",
                        "position": 25,
                    },
                },
                {
                    "trigger": {
                        "platform": "event",
                        "event_type": "test_event_set_tilt_pos",
                    },
                    "action": {
                        "domain": DOMAIN,
                        "device_id": "abcdefgh",
                        "entity_id": "cover.entity",
                        "type": "set_tilt_position",
                        "position": 75,
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    cover_pos_calls = async_mock_service(hass, "cover", "set_cover_position")
    tilt_pos_calls = async_mock_service(hass, "cover", "set_cover_tilt_position")

    hass.bus.async_fire("test_event_set_pos")
    await hass.async_block_till_done()
    assert len(cover_pos_calls) == 1
    assert cover_pos_calls[0].data["position"] == 25
    assert len(tilt_pos_calls) == 0

    hass.bus.async_fire("test_event_set_tilt_pos")
    await hass.async_block_till_done()
    assert len(cover_pos_calls) == 1
    assert len(tilt_pos_calls) == 1
    assert tilt_pos_calls[0].data["tilt_position"] == 75
