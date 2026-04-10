"""The tests for the Template alarm control panel platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_get_flow_preview_state,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry, mock_restore_cache
from tests.conftest import WebSocketGenerator

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_PANEL = TemplatePlatformSetup(
    ALARM_DOMAIN,
    "panels",
    "test_template_panel",
    make_test_trigger(TEST_STATE_ENTITY_ID, TEST_AVAILABILITY_ENTITY),
)


DATA_CODE = {"code": "{{ code }}"}
ARM_AWAY_ACTION = make_test_action("arm_away", DATA_CODE)
ARM_HOME_ACTION = make_test_action("arm_home", DATA_CODE)
ARM_NIGHT_ACTION = make_test_action("arm_night", DATA_CODE)
ARM_VACATION_ACTION = make_test_action("arm_vacation", DATA_CODE)
ARM_CUSTOM_BYPASS_ACTION = make_test_action("arm_custom_bypass", DATA_CODE)
DISARM_ACTION = make_test_action("disarm", DATA_CODE)
TRIGGER_ACTION = make_test_action("trigger", DATA_CODE)

OPTIMISTIC_ACTIONS = {
    **ARM_AWAY_ACTION,
    **ARM_HOME_ACTION,
    **ARM_NIGHT_ACTION,
    **ARM_VACATION_ACTION,
    **ARM_CUSTOM_BYPASS_ACTION,
    **DISARM_ACTION,
    **TRIGGER_ACTION,
}

EMPTY_ACTIONS = {action: [] for action in OPTIMISTIC_ACTIONS}


@pytest.fixture
async def setup_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    panel_config: dict[str, Any],
) -> None:
    """Do setup of alarm control panel integration."""
    await setup_entity(hass, TEST_PANEL, style, count, panel_config)


async def async_setup_state_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of alarm control panel integration using a state template."""
    await setup_entity(
        hass, TEST_PANEL, style, count, OPTIMISTIC_ACTIONS, state_template
    )


@pytest.fixture
async def setup_state_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of alarm control panel integration using a state template."""
    await setup_entity(
        hass, TEST_PANEL, style, count, OPTIMISTIC_ACTIONS, state_template
    )


@pytest.fixture
async def setup_base_panel(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    panel_config: str,
):
    """Do setup of alarm control panel integration using a state template."""
    await setup_entity(hass, TEST_PANEL, style, count, panel_config, state_template)


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
    await setup_entity(
        hass,
        TEST_PANEL,
        style,
        count,
        OPTIMISTIC_ACTIONS,
        state_template,
        {attribute: attribute_template} if attribute and attribute_template else {},
    )


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('sensor.test_state') }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
        await async_trigger(hass, TEST_STATE_ENTITY_ID, set_state)
        state = hass.states.get(TEST_PANEL.entity_id)
        assert state.state == set_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "invalid_state")
    state = hass.states.get(TEST_PANEL.entity_id)
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
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_panel")
async def test_state_template_states(hass: HomeAssistant, expected: str) -> None:
    """Test the state template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)
    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "attribute"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "{% if states.sensor.test_state.state %}mdi:check{% endif %}",
            "icon",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_icon_template(hass: HomeAssistant, initial_state: str) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.attributes.get("icon") == initial_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "attribute"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "{% if states.sensor.test_state.state %}local/panel.png{% endif %}",
            "picture",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_picture_template(hass: HomeAssistant, initial_state: str) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.attributes.get("entity_picture") == initial_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.attributes["entity_picture"] == "local/panel.png"


async def test_setup_config_entry(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the config flow."""
    value_template = "{{ states('alarm_control_panel.one') }}"

    await async_trigger(hass, "alarm_control_panel.one", "armed_away", {})

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

    await async_trigger(hass, "alarm_control_panel.one", "disarmed", {})
    state = hass.states.get("alarm_control_panel.my_template")
    assert state.state == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(("count", "state_template"), [(1, None)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize("panel_config", [OPTIMISTIC_ACTIONS, EMPTY_ACTIONS])
@pytest.mark.usefixtures("setup_base_panel")
async def test_optimistic_states(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test the optimistic state."""

    state = hass.states.get(TEST_PANEL.entity_id)
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
            {"entity_id": TEST_PANEL.entity_id, "code": "1234"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert hass.states.get(TEST_PANEL.entity_id).state == set_state


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("panel_config", "state_template", "msg"),
    [
        (
            OPTIMISTIC_ACTIONS,
            "{% if blah %}",
            "invalid template",
        ),
        (
            {"code_format": "bad_format", **OPTIMISTIC_ACTIONS},
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
                            **OPTIMISTIC_ACTIONS,
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
        (ConfigurationStyle.LEGACY, TEST_PANEL.entity_id),
        (ConfigurationStyle.MODERN, "alarm_control_panel.template_alarm_panel"),
        (ConfigurationStyle.TRIGGER, "alarm_control_panel.unnamed_device"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_name(hass: HomeAssistant, test_entity_id: str) -> None:
    """Test the accessibility of the name attribute."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "disarmed")

    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.attributes.get("friendly_name") == "Template Alarm Panel"


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('sensor.test_state') }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("service", "expected_service"),
    [
        ("alarm_arm_home", "arm_home"),
        ("alarm_arm_away", "arm_away"),
        ("alarm_arm_night", "arm_night"),
        ("alarm_arm_vacation", "arm_vacation"),
        ("alarm_arm_custom_bypass", "arm_custom_bypass"),
        ("alarm_disarm", "disarm"),
        ("alarm_trigger", "trigger"),
    ],
)
@pytest.mark.usefixtures("setup_state_panel")
async def test_actions(
    hass: HomeAssistant, service: str, expected_service: str, calls: list[ServiceCall]
) -> None:
    """Test alarm actions."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {"entity_id": TEST_PANEL.entity_id, "code": "1234"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert_action(TEST_PANEL, calls, 1, expected_service, code=1234)


@pytest.mark.parametrize("config", [OPTIMISTIC_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one alarm control panel per id."""
    await setup_and_test_unique_id(hass, TEST_PANEL, style, config)


@pytest.mark.parametrize("config", [OPTIMISTIC_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to alarm control panel unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_PANEL, style, entity_registry, config
    )


@pytest.mark.parametrize(("count", "state_template"), [(1, "disarmed")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.attributes.get("code_format") == code_format
    assert state.attributes.get("code_arm_required") == code_arm_required


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states('sensor.test_state') }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        ALARM_DOMAIN,
        {"name": "My template", "state": "{{ 'disarmed' }}"},
    )

    assert state["state"] == AlarmControlPanelState.DISARMED


@pytest.mark.parametrize(
    ("count", "panel_config"),
    [
        (
            1,
            {
                "name": TEST_PANEL.object_id,
                "state": "{{ states('sensor.test_state') }}",
                **OPTIMISTIC_ACTIONS,
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_panel")
async def test_optimistic(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test configuration with empty script."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, AlarmControlPanelState.DISARMED)

    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {"entity_id": TEST_PANEL.entity_id, "code": "1234"},
        blocking=True,
    )

    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.state == AlarmControlPanelState.ARMED_AWAY

    await async_trigger(hass, TEST_STATE_ENTITY_ID, AlarmControlPanelState.ARMED_HOME)

    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.state == AlarmControlPanelState.ARMED_HOME


@pytest.mark.parametrize(
    ("count", "panel_config"),
    [
        (
            1,
            {
                "name": TEST_PANEL.object_id,
                "state": "{{ states('sensor.test_state') }}",
                **OPTIMISTIC_ACTIONS,
                "optimistic": False,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_panel")
async def test_not_optimistic(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        "alarm_arm_away",
        {"entity_id": TEST_PANEL.entity_id, "code": "1234"},
        blocking=True,
    )

    state = hass.states.get(TEST_PANEL.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("count", "state_template", "attribute", "attribute_template"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "availability",
            "{{ is_state('binary_sensor.availability', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    # When template returns true..
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_ON)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    # Device State should not be unavailable
    assert hass.states.get(TEST_PANEL.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_OFF)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    # device state should be unavailable
    assert hass.states.get(TEST_PANEL.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "state_template", "attribute", "attribute_template"),
    [
        (
            1,
            "{{ 'disarmed' }}",
            "availability",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_single_attribute_state_panel")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    assert hass.states.get(TEST_PANEL.entity_id).state != STATE_UNAVAILABLE
    error = "UndefinedError: 'x' is undefined"
    assert error in caplog_setup_text or error in caplog.text
