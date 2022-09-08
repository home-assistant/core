"""The tests for Cover device triggers."""
from datetime import timedelta

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.cover import (
    DOMAIN,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
)
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import (
    CONF_PLATFORM,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_fire_time_changed,
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


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.mark.parametrize(
    "set_state,features_reg,features_state,expected_trigger_types",
    [
        (False, SUPPORT_OPEN, 0, ["opened", "closed", "opening", "closing"]),
        (
            False,
            SUPPORT_OPEN | SUPPORT_SET_POSITION,
            0,
            ["opened", "closed", "opening", "closing", "position"],
        ),
        (
            False,
            SUPPORT_OPEN | SUPPORT_SET_TILT_POSITION,
            0,
            ["opened", "closed", "opening", "closing", "tilt_position"],
        ),
        (True, 0, SUPPORT_OPEN, ["opened", "closed", "opening", "closing"]),
        (
            True,
            0,
            SUPPORT_OPEN | SUPPORT_SET_POSITION,
            ["opened", "closed", "opening", "closing", "position"],
        ),
        (
            True,
            0,
            SUPPORT_OPEN | SUPPORT_SET_TILT_POSITION,
            ["opened", "closed", "opening", "closing", "tilt_position"],
        ),
    ],
)
async def test_get_triggers(
    hass,
    device_reg,
    entity_reg,
    set_state,
    features_reg,
    features_state,
    expected_trigger_types,
):
    """Test we get the expected triggers from a cover."""
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
            f"{DOMAIN}.test_5678",
            "attributes",
            {"supported_features": features_state},
        )

    expected_triggers = []

    expected_triggers += [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": False},
        }
        for trigger in expected_trigger_types
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


@pytest.mark.parametrize(
    "hidden_by,entity_category",
    (
        (RegistryEntryHider.INTEGRATION, None),
        (RegistryEntryHider.USER, None),
        (None, EntityCategory.CONFIG),
        (None, EntityCategory.DIAGNOSTIC),
    ),
)
async def test_get_triggers_hidden_auxiliary(
    hass,
    device_reg,
    entity_reg,
    hidden_by,
    entity_category,
):
    """Test we get the expected triggers from a hidden or auxiliary entity."""
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
        entity_category=entity_category,
        hidden_by=hidden_by,
        supported_features=SUPPORT_OPEN,
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": trigger,
            "device_id": device_entry.id,
            "entity_id": f"{DOMAIN}.test_5678",
            "metadata": {"secondary": True},
        }
        for trigger in ["opened", "closed", "opening", "closing"]
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_get_trigger_capabilities(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[0]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 4
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        assert capabilities == {
            "extra_fields": [
                {"name": "for", "optional": True, "type": "positive_time_period_dict"}
            ]
        }


async def test_get_trigger_capabilities_set_pos(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "above",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            },
            {
                "name": "below",
                "optional": True,
                "type": "integer",
                "default": 100,
                "valueMax": 100,
                "valueMin": 0,
            },
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 5
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        if trigger["type"] == "position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {
                "extra_fields": [
                    {
                        "name": "for",
                        "optional": True,
                        "type": "positive_time_period_dict",
                    }
                ]
            }


async def test_get_trigger_capabilities_set_tilt_pos(
    hass, device_reg, entity_reg, enable_custom_integrations
):
    """Test we get the expected capabilities from a cover trigger."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[3]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_reg.async_get_or_create(
        DOMAIN, "test", ent.unique_id, device_id=device_entry.id
    )

    expected_capabilities = {
        "extra_fields": [
            {
                "name": "above",
                "optional": True,
                "type": "integer",
                "default": 0,
                "valueMax": 100,
                "valueMin": 0,
            },
            {
                "name": "below",
                "optional": True,
                "type": "integer",
                "default": 100,
                "valueMax": 100,
                "valueMin": 0,
            },
        ]
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 5
    for trigger in triggers:
        capabilities = await async_get_device_automation_capabilities(
            hass, DeviceAutomationType.TRIGGER, trigger
        )
        if trigger["type"] == "tilt_position":
            assert capabilities == expected_capabilities
        else:
            assert capabilities == {
                "extra_fields": [
                    {
                        "name": "for",
                        "optional": True,
                        "type": "positive_time_period_dict",
                    }
                ]
            }


async def test_if_fires_on_state_change(hass, calls):
    """Test for state triggers firing."""
    hass.states.async_set("cover.entity", STATE_CLOSED)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "cover.entity",
                        "type": "opened",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "opened - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "cover.entity",
                        "type": "closed",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "closed - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "cover.entity",
                        "type": "opening",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "opening - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": "cover.entity",
                        "type": "closing",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "closing - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )

    # Fake that the entity is opened.
    hass.states.async_set("cover.entity", STATE_OPEN)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data[
        "some"
    ] == "opened - device - {} - closed - open - None".format("cover.entity")

    # Fake that the entity is closed.
    hass.states.async_set("cover.entity", STATE_CLOSED)
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data[
        "some"
    ] == "closed - device - {} - open - closed - None".format("cover.entity")

    # Fake that the entity is opening.
    hass.states.async_set("cover.entity", STATE_OPENING)
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert calls[2].data[
        "some"
    ] == "opening - device - {} - closed - opening - None".format("cover.entity")

    # Fake that the entity is closing.
    hass.states.async_set("cover.entity", STATE_CLOSING)
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert calls[3].data[
        "some"
    ] == "closing - device - {} - opening - closing - None".format("cover.entity")


async def test_if_fires_on_state_change_with_for(hass, calls):
    """Test for triggers firing with delay."""
    entity_id = "cover.entity"
    hass.states.async_set(entity_id, STATE_CLOSED)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": "",
                        "entity_id": entity_id,
                        "type": "opened",
                        "for": {"seconds": 5},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "turn_off {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(
                                (
                                    "platform",
                                    "entity_id",
                                    "from_state.state",
                                    "to_state.state",
                                    "for",
                                )
                            )
                        },
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_CLOSED
    assert len(calls) == 0

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert (
        calls[0].data["some"]
        == f"turn_off device - {entity_id} - closed - open - 0:00:05"
    )


async def test_if_fires_on_position(hass, calls, enable_custom_integrations):
    """Test for position triggers."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "position",
                            "above": 45,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_gt_45 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "position",
                            "below": 90,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_lt_90 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "position",
                            "above": 45,
                            "below": 90,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_gt_45_lt_90 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    hass.states.async_set(ent.entity_id, STATE_OPEN, attributes={"current_position": 1})
    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_position": 95}
    )
    hass.states.async_set(
        ent.entity_id, STATE_OPEN, attributes={"current_position": 50}
    )
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert sorted(
        [calls[0].data["some"], calls[1].data["some"], calls[2].data["some"]]
    ) == sorted(
        [
            "is_pos_gt_45_lt_90 - device - cover.set_position_cover - closed - open - None",
            "is_pos_lt_90 - device - cover.set_position_cover - closed - open - None",
            "is_pos_gt_45 - device - cover.set_position_cover - open - closed - None",
        ]
    )

    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_position": 95}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_position": 45}
    )
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert (
        calls[3].data["some"]
        == "is_pos_lt_90 - device - cover.set_position_cover - closed - closed - None"
    )

    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_position": 90}
    )
    await hass.async_block_till_done()
    assert len(calls) == 5
    assert (
        calls[4].data["some"]
        == "is_pos_gt_45 - device - cover.set_position_cover - closed - closed - None"
    )


async def test_if_fires_on_tilt_position(hass, calls, enable_custom_integrations):
    """Test for tilt position triggers."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()
    ent = platform.ENTITIES[1]
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "tilt_position",
                            "above": 45,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_gt_45 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "tilt_position",
                            "below": 90,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_lt_90 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
                {
                    "trigger": [
                        {
                            "platform": "device",
                            "domain": DOMAIN,
                            "device_id": "",
                            "entity_id": ent.entity_id,
                            "type": "tilt_position",
                            "above": 45,
                            "below": 90,
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "is_pos_gt_45_lt_90 - {{ trigger.platform}} - "
                                "{{ trigger.entity_id}} - {{ trigger.from_state.state}} - "
                                "{{ trigger.to_state.state}} - {{ trigger.for }}"
                            )
                        },
                    },
                },
            ]
        },
    )
    hass.states.async_set(
        ent.entity_id, STATE_OPEN, attributes={"current_tilt_position": 1}
    )
    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_tilt_position": 95}
    )
    hass.states.async_set(
        ent.entity_id, STATE_OPEN, attributes={"current_tilt_position": 50}
    )
    await hass.async_block_till_done()
    assert len(calls) == 3
    assert sorted(
        [calls[0].data["some"], calls[1].data["some"], calls[2].data["some"]]
    ) == sorted(
        [
            "is_pos_gt_45_lt_90 - device - cover.set_position_cover - closed - open - None",
            "is_pos_lt_90 - device - cover.set_position_cover - closed - open - None",
            "is_pos_gt_45 - device - cover.set_position_cover - open - closed - None",
        ]
    )

    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_tilt_position": 95}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_tilt_position": 45}
    )
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert (
        calls[3].data["some"]
        == "is_pos_lt_90 - device - cover.set_position_cover - closed - closed - None"
    )

    hass.states.async_set(
        ent.entity_id, STATE_CLOSED, attributes={"current_tilt_position": 90}
    )
    await hass.async_block_till_done()
    assert len(calls) == 5
    assert (
        calls[4].data["some"]
        == "is_pos_gt_45 - device - cover.set_position_cover - closed - closed - None"
    )
