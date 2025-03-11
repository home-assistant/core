"""The tests for the  Template switch platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import switch, template
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.template.switch import rewrite_legacy_to_modern_conf
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_component,
    mock_restore_cache,
)

TEST_OBJECT_ID = "test_template_switch"
TEST_ENTITY_ID = f"switch.{TEST_OBJECT_ID}"
SWITCH_ACTIONS = {
    "turn_on": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_on",
            "caller": "{{ this.entity_id }}",
        },
    },
    "turn_off": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_off",
            "caller": "{{ this.entity_id }}",
        },
    },
}
NAMED_SWITCH_ACTIONS = {
    **SWITCH_ACTIONS,
    "name": TEST_OBJECT_ID,
}


def _create_template_config(state_template: str) -> list[tuple[dict, str]]:
    return [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": state_template,
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": state_template,
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ]


async def test_legacy_to_modern_config(hass: HomeAssistant) -> None:
    """Test the conversion of legacy template to modern template."""
    config = {
        "foo": {
            "friendly_name": "foo bar",
            "value_template": "{{ 1 == 1 }}",
            "unique_id": "foo-bar-switch",
            "icon_template": "{{ 'mdi.abc' }}",
            "entity_picture_template": "{{ 'mypicture.jpg' }}",
            "availability_template": "{{ 1 == 1 }}",
            **SWITCH_ACTIONS,
        }
    }
    altered_configs = rewrite_legacy_to_modern_conf(hass, config)

    assert len(altered_configs) == 1

    altered_config = altered_configs[0]

    assert "object_id" in altered_config
    assert altered_config["object_id"] == "foo"

    assert "friendly_name" not in altered_config
    assert "name" in altered_config
    assert altered_config["name"].template == "foo bar"

    assert "value_template" not in altered_config
    assert "state" in altered_config
    assert altered_config["state"].template == "{{ 1 == 1 }}"

    assert "icon_template" not in altered_config
    assert "icon" in altered_config
    assert altered_config["icon"].template == "{{ 'mdi.abc' }}"

    assert "entity_picture_template" not in altered_config
    assert "picture" in altered_config
    assert altered_config["picture"].template == "{{ 'mypicture.jpg' }}"

    assert "availability_template" not in altered_config
    assert "availability" in altered_config
    assert altered_config["availability"].template == "{{ 1 == 1 }}"

    assert "unique_id" in altered_config
    assert altered_config["unique_id"] == "foo-bar-switch"

    assert "turn_on" in altered_config
    assert altered_config["turn_on"] == {
        "service": "test.automation",
        "data_template": {
            "action": "turn_on",
            "caller": "{{ this.entity_id }}",
        },
    }

    assert "turn_off" in altered_config
    assert altered_config["turn_off"] == {
        "service": "test.automation",
        "data_template": {
            "action": "turn_off",
            "caller": "{{ this.entity_id }}",
        },
    }


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(("config", "domain"), _create_template_config("{{ True }}"))
@pytest.mark.usefixtures("start_ha")
async def test_setup(hass: HomeAssistant) -> None:
    """Test template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.name == TEST_OBJECT_ID
    assert state.state == STATE_ON


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config flow."""

    hass.states.async_set(
        "switch.one",
        "on",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('switch.one') }}",
            "template_type": SWITCH_DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.my_template")
    assert state is not None
    assert state == snapshot


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{{ states.switch.test_state.state }}"),
)
async def test_template_state_text(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test the state text of a template."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{{ 1 == 1 }}"),
)
async def test_template_state_boolean_on(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test the setting of the state with boolean on."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{{ 1 == 2 }}"),
)
async def test_template_state_boolean_off(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test the setting of the state with off."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ states.switch.test_state.state }}",
                        "icon": (
                            "{% if states.switch.test_state.state %}"
                            "mdi:check"
                            "{% endif %}"
                        ),
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ states.switch.test_state.state }}",
                            "icon_template": (
                                "{% if states.switch.test_state.state %}"
                                "mdi:check"
                                "{% endif %}"
                            ),
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_icon_template(hass: HomeAssistant, config: dict, domain: str) -> None:
    """Test the state text of a template."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes.get("icon") == ""

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ states.switch.test_state.state }}",
                        "picture": (
                            "{% if states.switch.test_state.state %}"
                            "/local/switch.png"
                            "{% endif %}"
                        ),
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ states.switch.test_state.state }}",
                            "entity_picture_template": (
                                "{% if states.switch.test_state.state %}"
                                "/local/switch.png"
                                "{% endif %}"
                            ),
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_entity_picture_template(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test entity_picture template."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes.get("entity_picture") == ""

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{% if rubbish %}"),
)
async def test_template_syntax_error(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test templating syntax error."""
    with assert_setup_component(0, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


async def test_invalid_legacy_slug_does_not_create(hass: HomeAssistant) -> None:
    """Test invalid legacy slug."""
    with assert_setup_component(0, "switch"):
        assert await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "test INVALID switch": {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ rubbish }",
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {"switch": "Invalid"},
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {TEST_OBJECT_ID: "Invalid"},
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_invalid_switch_does_not_create(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test invalid switch."""
    with assert_setup_component(0, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("config", "domain", "count"),
    [
        (
            {
                "template": {"switch": []},
            },
            template.DOMAIN,
            1,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                }
            },
            switch.DOMAIN,
            0,
        ),
    ],
)
async def test_no_switches_does_not_create(
    hass: HomeAssistant, config: dict, domain: str, count: int
) -> None:
    """Test if there are no switches no creation."""
    with assert_setup_component(count, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        "not_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "turn_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                        "state": "{{ states.switch.test_state.state }}",
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            "not_on": {
                                "service": "switch.turn_on",
                                "entity_id": "switch.test_state",
                            },
                            "turn_off": {
                                "service": "switch.turn_off",
                                "entity_id": "switch.test_state",
                            },
                            "value_template": "{{ states.switch.test_state.state }}",
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_missing_on_does_not_create(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test missing on."""
    with assert_setup_component(0, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        "turn_on": {
                            "service": "switch.turn_on",
                            "entity_id": "switch.test_state",
                        },
                        "not_off": {
                            "service": "switch.turn_off",
                            "entity_id": "switch.test_state",
                        },
                        "state": "{{ states.switch.test_state.state }}",
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            "turn_on": {
                                "service": "switch.turn_on",
                                "entity_id": "switch.test_state",
                            },
                            "not_off": {
                                "service": "switch.turn_off",
                                "entity_id": "switch.test_state",
                            },
                            "value_template": "{{ states.switch.test_state.state }}",
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_missing_off_does_not_create(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test missing off."""
    with assert_setup_component(0, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{{ states.switch.test_state.state }}"),
)
async def test_on_action(
    hass: HomeAssistant, config: dict, domain: str, calls: list[ServiceCall]
) -> None:
    """Test on action."""
    assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_template_switch"},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "switch.test_template_switch"


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_on_action_optimistic(
    hass: HomeAssistant, config: dict, domain: str, calls: list[ServiceCall]
) -> None:
    """Test on action in optimistic mode."""
    assert await async_setup_component(hass, domain, config)

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_template_switch", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_template_switch"},
        blocking=True,
    )

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "switch.test_template_switch"


@pytest.mark.parametrize(
    ("config", "domain"),
    _create_template_config("{{ states.switch.test_state.state }}"),
)
async def test_off_action(
    hass: HomeAssistant, config: dict, domain: str, calls: list[ServiceCall]
) -> None:
    """Test off action."""
    assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_template_switch"},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == "switch.test_template_switch"


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_off_action_optimistic(
    hass: HomeAssistant, config: dict, domain: str, calls: list[ServiceCall]
) -> None:
    """Test off action in optimistic mode."""
    assert await async_setup_component(hass, domain, config)

    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_template_switch", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_template_switch"},
        blocking=True,
    )

    state = hass.states.get("switch.test_template_switch")
    assert state.state == STATE_OFF

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == "switch.test_template_switch"


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test state restoration."""
    mock_restore_cache(
        hass,
        (
            State("switch.s1", STATE_ON),
            State("switch.s2", STATE_OFF),
        ),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "s1": {
                        **SWITCH_ACTIONS,
                    },
                    "s2": {
                        **SWITCH_ACTIONS,
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.s1")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("switch.s2")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ 1 == 1 }}",
                        "availability": (
                            "{{ is_state('availability_state.state', 'on') }}"
                        ),
                    }
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ 1 == 1 }}",
                            "availability_template": (
                                "{{ is_state('availability_state.state', 'on') }}"
                            ),
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_available_template_with_entities(
    hass: HomeAssistant, config: dict, domain: str
) -> None:
    """Test availability templates with values from other entities."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state != STATE_UNAVAILABLE

    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "template",
                "switches": {
                    "test_template_switch": {
                        **SWITCH_ACTIONS,
                        "value_template": "{{ true }}",
                        "availability_template": "{{ x - 12 }}",
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_template_switch").state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog.text


@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "template": {
                    "switch": [
                        {
                            **SWITCH_ACTIONS,
                            "name": "test_template_switch_01",
                            "unique_id": "not-so-unique-anymore",
                            "state": "{{ true }}",
                        },
                        {
                            **SWITCH_ACTIONS,
                            "name": "test_template_switch_02",
                            "unique_id": "not-so-unique-anymore",
                            "state": "{{ true }}",
                        },
                    ]
                },
            },
            template.DOMAIN,
        ),
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        "test_template_switch_01": {
                            **SWITCH_ACTIONS,
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ true }}",
                        },
                        "test_template_switch_02": {
                            **SWITCH_ACTIONS,
                            "unique_id": "not-so-unique-anymore",
                            "value_template": "{{ false }}",
                        },
                    },
                }
            },
            switch.DOMAIN,
        ),
    ],
)
async def test_unique_id(hass: HomeAssistant, config: dict, domain: str) -> None:
    """Test unique_id option only creates one switch per id."""
    with assert_setup_component(1, domain):
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("switch")) == 1


async def test_template_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    with assert_setup_component(1, "template"):
        assert await async_setup_component(
            hass,
            "template",
            {
                "template": {
                    "unique_id": "x",
                    "switch": [
                        {
                            **SWITCH_ACTIONS,
                            "name": "test_a",
                            "unique_id": "a",
                            "state": "{{ true }}",
                        },
                        {
                            **SWITCH_ACTIONS,
                            "name": "test_b",
                            "unique_id": "b",
                            "state": "{{ true }}",
                        },
                    ],
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("switch")) == 2

    entry = entity_registry.async_get("switch.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("switch.test_b")
    assert entry
    assert entry.unique_id == "x-b"


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for Template."""

    device_config_entry = MockConfigEntry()
    device_config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=device_config_entry.entry_id,
        identifiers={("test", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    await hass.async_block_till_done()
    assert device_entry is not None
    assert device_entry.id is not None

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ true }}",
            "template_type": "switch",
            "device_id": device_entry.id,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("switch.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id
