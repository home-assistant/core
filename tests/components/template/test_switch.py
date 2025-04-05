"""The tests for the  Template switch platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import switch, template
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.template.switch import rewrite_legacy_to_modern_conf
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_component,
    mock_restore_cache,
)
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_template_switch"
TEST_ENTITY_ID = f"switch.{TEST_OBJECT_ID}"
TEST_STATE_ENTITY_ID = "switch.test_state"

SWITCH_TURN_ON = {
    "service": "test.automation",
    "data_template": {
        "action": "turn_on",
        "caller": "{{ this.entity_id }}",
    },
}
SWITCH_TURN_OFF = {
    "service": "test.automation",
    "data_template": {
        "action": "turn_off",
        "caller": "{{ this.entity_id }}",
    },
}
SWITCH_ACTIONS = {
    "turn_on": SWITCH_TURN_ON,
    "turn_off": SWITCH_TURN_OFF,
}
NAMED_SWITCH_ACTIONS = {
    **SWITCH_ACTIONS,
    "name": TEST_OBJECT_ID,
}
UNIQUE_ID_CONFIG = {
    **SWITCH_ACTIONS,
    "unique_id": "not-so-unique-anymore",
}


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, switch_config: dict[str, Any]
) -> None:
    """Do setup of switch integration via legacy format."""
    config = {"switch": {"platform": "template", "switches": switch_config}}

    with assert_setup_component(count, switch.DOMAIN):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            config,
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, switch_config: dict[str, Any]
) -> None:
    """Do setup of switch integration via modern format."""
    config = {"template": {"switch": switch_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def setup_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    switch_config: dict[str, Any],
) -> None:
    """Do setup of switch integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, switch_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, switch_config)


@pytest.fixture
async def setup_state_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of switch integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **SWITCH_ACTIONS,
                    "value_template": state_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_SWITCH_ACTIONS,
                "state": state_template,
            },
        )


@pytest.fixture
async def setup_single_attribute_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of switch integration testing a single attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **SWITCH_ACTIONS,
                    "value_template": "{{ 1 == 1 }}",
                    **extra,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_SWITCH_ACTIONS,
                "state": "{{ 1 == 1 }}",
                **extra,
            },
        )


@pytest.fixture
async def setup_optimistic_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
) -> None:
    """Do setup of an optimistic switch."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **SWITCH_ACTIONS,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_SWITCH_ACTIONS,
            },
        )


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
    assert [
        {
            "availability": Template("{{ 1 == 1 }}", hass),
            "icon": Template("{{ 'mdi.abc' }}", hass),
            "name": Template("foo bar", hass),
            "object_id": "foo",
            "picture": Template("{{ 'mypicture.jpg' }}", hass),
            "turn_off": SWITCH_TURN_OFF,
            "turn_on": SWITCH_TURN_ON,
            "unique_id": "foo-bar-switch",
            "state": Template("{{ 1 == 1 }}", hass),
        }
    ] == altered_configs


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ True }}")])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_setup(hass: HomeAssistant, setup_state_switch) -> None:
    """Test template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.name == TEST_OBJECT_ID
    assert state.state == STATE_ON


@pytest.mark.parametrize("state_key", ["value_template", "state"])
async def test_setup_config_entry(
    hass: HomeAssistant,
    state_key: str,
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
            state_key: "{{ states('switch.one') }}",
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


@pytest.mark.parametrize("state_key", ["value_template", "state"])
async def test_flow_preview(
    hass: HomeAssistant,
    state_key: str,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        template.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": SWITCH_DOMAIN},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SWITCH_DOMAIN
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", state_key: "{{ 'on' }}"},
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"]["state"] == "on"


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.switch.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_template_state_text(hass: HomeAssistant, setup_state_switch) -> None:
    """Test the state text of a template."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("expected", "state_template"),
    [
        (STATE_ON, "{{ 1 == 1 }}"),
        (STATE_OFF, "{{ 1 == 2 }}"),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_template_state_boolean(
    hass: HomeAssistant, expected: str, setup_state_switch
) -> None:
    """Test the setting of the state with boolean template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{% if states.switch.test_state.state %}mdi:check{% endif %}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "icon_template"),
        (ConfigurationStyle.MODERN, "icon"),
    ],
)
async def test_icon_template(
    hass: HomeAssistant, setup_single_attribute_switch
) -> None:
    """Test the state text of a template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") == ""

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{% if states.switch.test_state.state %}/local/switch.png{% endif %}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template"),
        (ConfigurationStyle.MODERN, "picture"),
    ],
)
async def test_entity_picture_template(
    hass: HomeAssistant, setup_single_attribute_switch
) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") == ""

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(("count", "state_template"), [(0, "{% if rubbish %}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
async def test_template_syntax_error(hass: HomeAssistant, setup_state_switch) -> None:
    """Test templating syntax error."""
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
                        "not_on": SWITCH_TURN_ON,
                        "turn_off": SWITCH_TURN_OFF,
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
                            "not_on": SWITCH_TURN_ON,
                            "turn_off": SWITCH_TURN_OFF,
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
                        "turn_on": SWITCH_TURN_ON,
                        "not_off": SWITCH_TURN_OFF,
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
                            "turn_on": SWITCH_TURN_ON,
                            "not_off": SWITCH_TURN_OFF,
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
    ("count", "state_template"), [(1, "{{ states('switch.test_state') }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_on_action(
    hass: HomeAssistant, setup_state_switch, calls: list[ServiceCall]
) -> None:
    """Test on action."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_on_action_optimistic(
    hass: HomeAssistant, setup_optimistic_switch, calls: list[ServiceCall]
) -> None:
    """Test on action in optimistic mode."""
    hass.states.async_set(TEST_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.switch.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_off_action(
    hass: HomeAssistant, setup_state_switch, calls: list[ServiceCall]
) -> None:
    """Test off action."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
async def test_off_action_optimistic(
    hass: HomeAssistant, setup_optimistic_switch, calls: list[ServiceCall]
) -> None:
    """Test off action in optimistic mode."""
    hass.states.async_set(TEST_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
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
            switch.DOMAIN,
        ),
        (
            {
                "template": {
                    "switch": [
                        {
                            "name": "s1",
                            **SWITCH_ACTIONS,
                        },
                        {
                            "name": "s2",
                            **SWITCH_ACTIONS,
                        },
                    ],
                }
            },
            template.DOMAIN,
        ),
    ],
)
async def test_restore_state(
    hass: HomeAssistant, count: int, domain: str, config: dict[str, Any]
) -> None:
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

    with assert_setup_component(count, domain):
        await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()

    state = hass.states.get("switch.s1")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("switch.s2")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{{ is_state('switch.test_state', 'on') }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
    ],
)
async def test_available_template_with_entities(
    hass: HomeAssistant, setup_single_attribute_switch
) -> None:
    """Test availability templates with values from other entities."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "domain"),
    [
        (
            {
                "switch": {
                    "platform": "template",
                    "switches": {
                        TEST_OBJECT_ID: {
                            **SWITCH_ACTIONS,
                            "value_template": "{{ true }}",
                            "availability_template": "{{ x - 12 }}",
                        }
                    },
                }
            },
            switch.DOMAIN,
        ),
        (
            {
                "template": {
                    "switch": {
                        **NAMED_SWITCH_ACTIONS,
                        "state": "{{ true }}",
                        "availability": "{{ x - 12 }}",
                    },
                }
            },
            template.DOMAIN,
        ),
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    count: int,
    config: dict[str, Any],
    domain: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an invalid availability keeps the device available."""
    with assert_setup_component(count, domain):
        await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog.text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("switch_config", "style"),
    [
        (
            {
                "test_template_switch_01": UNIQUE_ID_CONFIG,
                "test_template_switch_02": UNIQUE_ID_CONFIG,
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_switch_01",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_switch_02",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
    ],
)
async def test_unique_id(hass: HomeAssistant, setup_switch) -> None:
    """Test unique_id option only creates one switch per id."""
    assert len(hass.states.async_all("switch")) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "switch_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                TEST_OBJECT_ID: {
                    "turn_on": [],
                    "turn_off": [],
                },
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "name": TEST_OBJECT_ID,
                "turn_on": [],
                "turn_off": [],
            },
        ),
    ],
)
async def test_empty_action_config(hass: HomeAssistant, setup_switch) -> None:
    """Test configuration with empty script."""
    await hass.services.async_call(
        switch.DOMAIN,
        switch.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        switch.DOMAIN,
        switch.SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
