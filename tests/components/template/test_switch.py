"""The tests for the  Template switch platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import switch, template
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    mock_component,
    mock_restore_cache,
)
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_template_switch"
TEST_STATE_ENTITY_ID = "switch.test_state"
TEST_SENSOR = "sensor.test_sensor"

TEST_SWITCH = TemplatePlatformSetup(
    switch.DOMAIN,
    "switches",
    "test_template_switch",
    make_test_trigger(TEST_STATE_ENTITY_ID, TEST_SENSOR),
)

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


@pytest.fixture
async def setup_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    switch_config: dict[str, Any],
) -> None:
    """Do setup of switch integration."""
    await setup_entity(hass, TEST_SWITCH, style, count, switch_config)


@pytest.fixture
async def setup_state_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of switch integration using a state template."""
    await setup_entity(
        hass, TEST_SWITCH, style, count, SWITCH_ACTIONS, state_template=state_template
    )


@pytest.fixture
async def setup_state_switch_with_extra(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    config: ConfigType,
):
    """Do setup of switch integration using a state template."""
    await setup_entity(
        hass, TEST_SWITCH, style, count, config, state_template=state_template
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
    await setup_entity(
        hass,
        TEST_SWITCH,
        style,
        count,
        SWITCH_ACTIONS,
        state_template="{{ 1 == 1 }}",
        extra_config=(
            {attribute: attribute_template} if attribute and attribute_template else {}
        ),
    )


@pytest.fixture
async def setup_optimistic_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
) -> None:
    """Do setup of an optimistic switch."""
    await setup_entity(hass, TEST_SWITCH, style, count, SWITCH_ACTIONS)


@pytest.fixture
async def setup_single_attribute_optimistic_switch(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of switch integration testing a single attribute."""
    await setup_entity(
        hass,
        TEST_SWITCH,
        style,
        count,
        SWITCH_ACTIONS,
        extra_config=(
            {attribute: attribute_template} if attribute and attribute_template else {}
        ),
    )


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ True }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_setup(hass: HomeAssistant) -> None:
    """Test template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID)
    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state is not None
    assert state.name == TEST_SWITCH.object_id
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

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        switch.DOMAIN,
        {"name": "My template", state_key: "{{ 'on' }}"},
    )

    assert state["state"] == STATE_ON


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.switch.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_SWITCH.entity_id)
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
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_template_state_boolean(hass: HomeAssistant, expected: str) -> None:
    """Test the setting of the state with boolean template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID)
    state = hass.states.get(TEST_SWITCH.entity_id)
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
        (ConfigurationStyle.TRIGGER, "icon"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_switch")
async def test_icon_template(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.attributes.get("icon") in ("", None)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{{ states('sensor.test_sensor') }}")],
)
@pytest.mark.parametrize("style", [ConfigurationStyle.TRIGGER])
@pytest.mark.parametrize(
    ("attribute", "attr", "expected"),
    [("icon", "icon", "mdi:icon"), ("picture", "entity_picture", "picture.jpg")],
)
@pytest.mark.usefixtures("setup_single_attribute_optimistic_switch")
async def test_trigger_attributes_with_optimistic_state(
    hass: HomeAssistant,
    attr: str,
    expected: str,
    calls: list[ServiceCall],
) -> None:
    """Test attributes when trigger entity is optimistic."""
    hass.states.async_set(TEST_SWITCH.entity_id, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes.get(attr) is None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(attr) is None

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes.get(attr) is None

    assert len(calls) == 2
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id

    await async_trigger(hass, TEST_SENSOR, expected)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes.get(attr) == expected

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(attr) == expected

    assert len(calls) == 3
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{% if states.switch.test_state.state %}/local/switch.png{% endif %}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template"),
        (ConfigurationStyle.MODERN, "picture"),
        (ConfigurationStyle.TRIGGER, "picture"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_switch")
async def test_entity_picture_template(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.attributes.get("entity_picture") in ("", None)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(("count", "state_template"), [(0, "{% if rubbish %}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_template_syntax_error(hass: HomeAssistant) -> None:
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
                    "switches": {TEST_SWITCH.object_id: "Invalid"},
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
    ("count", "state_template"), [(0, "{{ states.switch.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "not_on": SWITCH_TURN_ON,
            "turn_off": SWITCH_TURN_OFF,
        },
        {
            "turn_on": SWITCH_TURN_ON,
            "not_off": SWITCH_TURN_OFF,
        },
    ],
)
@pytest.mark.usefixtures("setup_state_switch_with_extra")
async def test_missing_action_does_not_create(hass: HomeAssistant) -> None:
    """Test missing actions."""
    assert hass.states.async_all("switch") == []


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('switch.test_state') }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_on_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test on action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_optimistic_switch")
async def test_on_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test on action in optimistic mode."""
    hass.states.async_set(TEST_SWITCH.entity_id, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.switch.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_switch")
async def test_off_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test off action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_optimistic_switch")
async def test_off_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test off action in optimistic mode."""
    hass.states.async_set(TEST_SWITCH.entity_id, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_SWITCH.entity_id


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize("test_state", [STATE_ON, STATE_OFF])
async def test_restore_state(
    hass: HomeAssistant, style: ConfigurationStyle, test_state: str
) -> None:
    """Test state restoration."""
    mock_restore_cache(
        hass,
        (State(TEST_SWITCH.entity_id, test_state),),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await setup_entity(hass, TEST_SWITCH, style, 1, SWITCH_ACTIONS)

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state
    assert state.state == test_state


@pytest.mark.parametrize(
    ("count", "attribute_template"),
    [(1, "{{ is_state('switch.test_state', 'on') }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_switch")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    assert hass.states.get(TEST_SWITCH.entity_id).state != STATE_UNAVAILABLE

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    assert hass.states.get(TEST_SWITCH.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("style", "config"),
    [
        (ConfigurationStyle.LEGACY, {"availability_template": "{{ x - 12 }}"}),
        (ConfigurationStyle.MODERN, {"availability": "{{ x - 12 }}"}),
        (ConfigurationStyle.TRIGGER, {"availability": "{{ x - 12 }}"}),
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an invalid availability keeps the device available."""
    await setup_entity(
        hass,
        TEST_SWITCH,
        style,
        1,
        config,
        extra_config=SWITCH_ACTIONS,
        state_template="{{ true }}",
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID)
    assert hass.states.get(TEST_SWITCH.entity_id).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog.text


@pytest.mark.parametrize("config", [SWITCH_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one switch per id."""
    await setup_and_test_unique_id(hass, TEST_SWITCH, style, config)


@pytest.mark.parametrize("config", [SWITCH_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_SWITCH, style, entity_registry, config
    )


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


@pytest.mark.parametrize(
    ("count", "switch_config"),
    [(1, {"turn_on": [], "turn_off": []})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_switch")
async def test_empty_action_config(hass: HomeAssistant) -> None:
    """Test configuration with empty script."""
    await hass.services.async_call(
        switch.DOMAIN,
        switch.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        switch.DOMAIN,
        switch.SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "switch_config"),
    [
        (
            1,
            {
                "state": "{{ is_state('switch.test_state', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_switch")
async def test_optimistic_option(hass: HomeAssistant) -> None:
    """Test optimistic yaml option."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        switch.DOMAIN,
        "turn_on",
        {"entity_id": TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_ON

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "switch_config"),
    [
        (
            1,
            {
                "state": "{{ is_state('switch.test_state', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": False,
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (ConfigurationStyle.MODERN, STATE_OFF),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_switch")
async def test_not_optimistic(hass: HomeAssistant, expected: str) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        switch.DOMAIN,
        "turn_on",
        {"entity_id": TEST_SWITCH.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_SWITCH.entity_id)
    assert state.state == expected
