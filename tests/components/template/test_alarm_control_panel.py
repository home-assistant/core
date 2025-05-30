"""The tests for the Template alarm control panel platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle

from tests.common import MockConfigEntry, assert_setup_component, mock_restore_cache

TEST_OBJECT_ID = "test_template_panel"
TEST_ENTITY_ID = f"alarm_control_panel.{TEST_OBJECT_ID}"
TEST_STATE_ENTITY_ID = "alarm_control_panel.test"


@pytest.fixture
def call_service_events(hass: HomeAssistant) -> list[Event]:
    """Track service call events for alarm_control_panel.test."""
    events: list[Event] = []
    entity_id = "alarm_control_panel.test"

    @callback
    def capture_events(event: Event) -> None:
        if event.data[ATTR_DOMAIN] != ALARM_DOMAIN:
            return
        if event.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID] != [entity_id]:
            return
        events.append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, capture_events)

    return events


OPTIMISTIC_TEMPLATE_ALARM_CONFIG = {
    "arm_away": {
        "service": "alarm_control_panel.alarm_arm_away",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_home": {
        "service": "alarm_control_panel.alarm_arm_home",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_night": {
        "service": "alarm_control_panel.alarm_arm_night",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_vacation": {
        "service": "alarm_control_panel.alarm_arm_vacation",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "arm_custom_bypass": {
        "service": "alarm_control_panel.alarm_arm_custom_bypass",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "disarm": {
        "service": "alarm_control_panel.alarm_disarm",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
    "trigger": {
        "service": "alarm_control_panel.alarm_trigger",
        "entity_id": "alarm_control_panel.test",
        "data": {"code": "{{ this.entity_id }}"},
    },
}
EMPTY_ACTIONS = {
    "arm_away": [],
    "arm_home": [],
    "arm_night": [],
    "arm_vacation": [],
    "arm_custom_bypass": [],
    "disarm": [],
    "trigger": [],
}


UNIQUE_ID_CONFIG = {
    **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
    "unique_id": "not-so-unique-anymore",
}


TEMPLATE_ALARM_CONFIG = {
    "value_template": "{{ states('alarm_control_panel.test') }}",
    **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
}


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, panel_config: dict[str, Any]
) -> None:
    """Do setup of alarm control panel integration via legacy format."""
    config = {"alarm_control_panel": {"platform": "template", "panels": panel_config}}

    with assert_setup_component(count, ALARM_DOMAIN):
        assert await async_setup_component(
            hass,
            ALARM_DOMAIN,
            config,
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, panel_config: dict[str, Any]
) -> None:
    """Do setup of alarm control panel integration via modern format."""
    config = {"template": {"alarm_control_panel": panel_config}}

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
async def setup_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    panel_config: dict[str, Any],
) -> None:
    """Do setup of alarm control panel integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, panel_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, panel_config)


async def async_setup_state_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of alarm control panel integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    "value_template": state_template,
                    **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "state": state_template,
                **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
            },
        )


@pytest.fixture
async def setup_state_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of alarm control panel integration using a state template."""
    await async_setup_state_panel(hass, count, style, state_template)


@pytest.fixture
async def setup_base_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    panel_config: str,
):
    """Do setup of alarm control panel integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        extra = {"value_template": state_template} if state_template else {}
        await async_setup_legacy_format(
            hass,
            count,
            {TEST_OBJECT_ID: {**extra, **panel_config}},
        )
    elif style == ConfigurationStyle.MODERN:
        extra = {"state": state_template} if state_template else {}
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **extra,
                **panel_config,
            },
        )


@pytest.fixture
async def setup_single_attribute_state_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of alarm control panel integration testing a single attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                    "value_template": state_template,
                    **extra,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                "state": state_template,
                **extra,
            },
        )


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('alarm_control_panel.test') }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.usefixtures("setup_state_panel")
async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""

    for set_state in (
        AlarmControlPanelState.ARMED_AWAY,
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        AlarmControlPanelState.ARMED_HOME,
        AlarmControlPanelState.ARMED_NIGHT,
        AlarmControlPanelState.ARMED_VACATION,
        AlarmControlPanelState.ARMING,
        AlarmControlPanelState.DISARMED,
        AlarmControlPanelState.DISARMING,
        AlarmControlPanelState.PENDING,
        AlarmControlPanelState.TRIGGERED,
    ):
        hass.states.async_set(TEST_STATE_ENTITY_ID, set_state)
        await hass.async_block_till_done()
        state = hass.states.get(TEST_ENTITY_ID)
        assert state.state == set_state

    hass.states.async_set(TEST_STATE_ENTITY_ID, "invalid_state")
    await hass.async_block_till_done()
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == "unknown"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ 'disarmed' }}", AlarmControlPanelState.DISARMED),
        ("{{ 'armed_home' }}", AlarmControlPanelState.ARMED_HOME),
        ("{{ 'armed_away' }}", AlarmControlPanelState.ARMED_AWAY),
        ("{{ 'armed_night' }}", AlarmControlPanelState.ARMED_NIGHT),
        ("{{ 'armed_vacation' }}", AlarmControlPanelState.ARMED_VACATION),
        ("{{ 'armed_custom_bypass' }}", AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        ("{{ 'pending' }}", AlarmControlPanelState.PENDING),
        ("{{ 'arming' }}", AlarmControlPanelState.ARMING),
        ("{{ 'disarming' }}", AlarmControlPanelState.DISARMING),
        ("{{ 'triggered' }}", AlarmControlPanelState.TRIGGERED),
        ("{{ x - 1 }}", STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.usefixtures("setup_state_panel")
async def test_state_template_states(hass: HomeAssistant, expected: str) -> None:
    """Test the state template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "{% if states.switch.test_state.state %}mdi:check{% endif %}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "icon"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_icon_template(
    hass: HomeAssistant,
) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") in ("", None)

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "{% if states.switch.test_state.state %}local/panel.png{% endif %}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "picture"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_picture_template(
    hass: HomeAssistant,
) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") in ("", None)

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["entity_picture"] == "local/panel.png"


async def test_setup_config_entry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the config flow."""
    value_template = "{{ states('alarm_control_panel.one') }}"

    hass.states.async_set("alarm_control_panel.one", "armed_away", {})

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "value_template": value_template,
            "template_type": "alarm_control_panel",
            "code_arm_required": True,
            "code_format": "number",
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("alarm_control_panel.my_template")
    assert state is not None
    assert state == snapshot

    hass.states.async_set("alarm_control_panel.one", "disarmed", {})
    await hass.async_block_till_done()
    state = hass.states.get("alarm_control_panel.my_template")
    assert state.state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(("count", "state_template"), [(1, None)])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    "panel_config", [OPTIMISTIC_TEMPLATE_ALARM_CONFIG, EMPTY_ACTIONS]
)
@pytest.mark.usefixtures("setup_base_panel")
async def test_optimistic_states(hass: HomeAssistant) -> None:
    """Test the optimistic state."""

    state = hass.states.get(TEST_ENTITY_ID)
    await hass.async_block_till_done()
    assert state.state == "unknown"

    for service, set_state in (
        ("alarm_arm_away", AlarmControlPanelState.ARMED_AWAY),
        ("alarm_arm_home", AlarmControlPanelState.ARMED_HOME),
        ("alarm_arm_night", AlarmControlPanelState.ARMED_NIGHT),
        ("alarm_arm_vacation", AlarmControlPanelState.ARMED_VACATION),
        ("alarm_arm_custom_bypass", AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        ("alarm_disarm", AlarmControlPanelState.DISARMED),
        ("alarm_trigger", AlarmControlPanelState.TRIGGERED),
    ):
        await hass.services.async_call(
            ALARM_DOMAIN,
            service,
            {"entity_id": TEST_ENTITY_ID, "code": "1234"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert hass.states.get(TEST_ENTITY_ID).state == set_state


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    ("panel_config", "state_template", "msg"),
    [
        (
            OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
            "{% if blah %}",
            "invalid template",
        ),
        (
            {"code_format": "bad_format", **OPTIMISTIC_TEMPLATE_ALARM_CONFIG},
            "disarmed",
            "value must be one of ['no_code', 'number', 'text']",
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_panel")
async def test_template_syntax_error(
    hass: HomeAssistant, msg, caplog_setup_text
) -> None:
    """Test templating syntax error."""
    assert len(hass.states.async_all("alarm_control_panel")) == 0
    assert (msg) in caplog_setup_text


@pytest.mark.parametrize(("count", "domain"), [(0, "alarm_control_panel")])
@pytest.mark.parametrize(
    ("config", "msg"),
    [
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "panels": {
                        "bad name here": {
                            "value_template": "disarmed",
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                        }
                    },
                }
            },
            "invalid slug bad name",
        ),
        (
            {
                "alarm_control_panel": {
                    "platform": "template",
                    "wibble": {"test_panel": "Invalid"},
                }
            },
            "'wibble' is an invalid option",
        ),
        (
            {
                "alarm_control_panel": {"platform": "template"},
            },
            "required key 'panels' not provided",
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_legacy_template_syntax_error(
    hass: HomeAssistant, msg, caplog_setup_text
) -> None:
    """Test templating syntax error."""
    assert len(hass.states.async_all("alarm_control_panel")) == 0
    assert (msg) in caplog_setup_text


@pytest.mark.parametrize(
    ("count", "state_template", "attribute", "attribute_template"),
    [(1, "disarmed", "name", '{{ "Template Alarm Panel" }}')],
)
@pytest.mark.parametrize(
    ("style", "test_entity_id"),
    [
        (ConfigurationStyle.LEGACY, TEST_ENTITY_ID),
        (ConfigurationStyle.MODERN, "alarm_control_panel.template_alarm_panel"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_name(hass: HomeAssistant, test_entity_id: str) -> None:
    """Test the accessibility of the name attribute."""
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.attributes.get("friendly_name") == "Template Alarm Panel"


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('alarm_control_panel.test') }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    "service",
    [
        "alarm_arm_home",
        "alarm_arm_away",
        "alarm_arm_night",
        "alarm_arm_vacation",
        "alarm_arm_custom_bypass",
        "alarm_disarm",
        "alarm_trigger",
    ],
)
@pytest.mark.usefixtures("setup_state_panel")
async def test_actions(
    hass: HomeAssistant, service, call_service_events: list[Event]
) -> None:
    """Test alarm actions."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {"entity_id": TEST_ENTITY_ID, "code": "1234"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(call_service_events) == 1
    assert call_service_events[0].data["service"] == service
    assert call_service_events[0].data["service_data"]["code"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("panel_config", "style"),
    [
        (
            {
                "test_template_alarm_control_panel_01": {
                    "value_template": "{{ true }}",
                    **UNIQUE_ID_CONFIG,
                },
                "test_template_alarm_control_panel_02": {
                    "value_template": "{{ false }}",
                    **UNIQUE_ID_CONFIG,
                },
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_alarm_control_panel_01",
                    "state": "{{ true }}",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_alarm_control_panel_02",
                    "state": "{{ false }}",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
    ],
)
@pytest.mark.usefixtures("setup_panel")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one alarm control panel per id."""
    assert len(hass.states.async_all()) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to alarm_control_panel unique_ids."""
    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "alarm_control_panel": [
                        {
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
                            "name": "test_a",
                            "unique_id": "a",
                            "state": "{{ true }}",
                        },
                        {
                            **OPTIMISTIC_TEMPLATE_ALARM_CONFIG,
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

    assert len(hass.states.async_all("alarm_control_panel")) == 2

    entry = entity_registry.async_get("alarm_control_panel.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("alarm_control_panel.test_b")
    assert entry
    assert entry.unique_id == "x-b"


@pytest.mark.parametrize(("count", "state_template"), [(1, "disarmed")])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    ("panel_config", "code_format", "code_arm_required"),
    [
        (
            {},
            "number",
            True,
        ),
        (
            {"code_format": "text"},
            "text",
            True,
        ),
        (
            {
                "code_format": "no_code",
                "code_arm_required": False,
            },
            None,
            False,
        ),
        (
            {
                "code_format": "text",
                "code_arm_required": False,
            },
            "text",
            False,
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_panel")
async def test_code_config(hass: HomeAssistant, code_format, code_arm_required) -> None:
    """Test configuration options related to alarm code."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("code_format") == code_format
    assert state.attributes.get("code_arm_required") == code_arm_required


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('alarm_control_panel.test') }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    ("restored_state", "initial_state"),
    [
        (
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_AWAY,
        ),
        (
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ),
        (
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_HOME,
        ),
        (
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_NIGHT,
        ),
        (
            AlarmControlPanelState.ARMED_VACATION,
            AlarmControlPanelState.ARMED_VACATION,
        ),
        (AlarmControlPanelState.ARMING, AlarmControlPanelState.ARMING),
        (AlarmControlPanelState.DISARMED, AlarmControlPanelState.DISARMED),
        (AlarmControlPanelState.PENDING, AlarmControlPanelState.PENDING),
        (
            AlarmControlPanelState.TRIGGERED,
            AlarmControlPanelState.TRIGGERED,
        ),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        (STATE_UNKNOWN, STATE_UNKNOWN),
        ("faulty_state", STATE_UNKNOWN),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    count: int,
    state_template: str,
    style: ConfigurationStyle,
    restored_state: str,
    initial_state: str,
) -> None:
    """Test restoring template alarm control panel."""

    fake_state = State(
        "alarm_control_panel.test_template_panel",
        restored_state,
        {},
    )
    mock_restore_cache(hass, (fake_state,))
    await async_setup_state_panel(hass, count, style, state_template)

    state = hass.states.get("alarm_control_panel.test_template_panel")
    assert state.state == initial_state


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for device for button template."""

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
            "value_template": "disarmed",
            "template_type": "alarm_control_panel",
            "code_arm_required": True,
            "code_format": "number",
            "device_id": device_entry.id,
        },
        title="My template",
    )

    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    template_entity = entity_registry.async_get("alarm_control_panel.my_template")
    assert template_entity is not None
    assert template_entity.device_id == device_entry.id
