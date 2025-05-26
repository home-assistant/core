"""Test the Switch config flow."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from homeassistant import config_entries
from homeassistant.components.template import DOMAIN, async_setup_entry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, get_schema_suggested_value
from tests.typing import WebSocketGenerator

SWITCH_BEFORE_OPTIONS = {
    "name": "test_template_switch",
    "template_type": "switch",
    "turn_off": [{"event": "test_template_switch", "event_data": {"event": "off"}}],
    "turn_on": [{"event": "test_template_switch", "event_data": {"event": "on"}}],
    "value_template": "{{ now().minute % 2 == 0 }}",
}


SWITCH_AFTER_OPTIONS = {
    "name": "test_template_switch",
    "template_type": "switch",
    "turn_off": [{"event": "test_template_switch", "event_data": {"event": "off"}}],
    "turn_on": [{"event": "test_template_switch", "event_data": {"event": "on"}}],
    "state": "{{ now().minute % 2 == 0 }}",
    "value_template": "{{ now().minute % 2 == 0 }}",
}

SENSOR_OPTIONS = {
    "name": "test_template_sensor",
    "template_type": "sensor",
    "state": "{{ 'a' if now().minute % 2 == 0 else 'b' }}",
}

BINARY_SENSOR_OPTIONS = {
    "name": "test_template_sensor",
    "template_type": "binary_sensor",
    "state": "{{ now().minute % 2 == 0 else }}",
}


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "template_state",
        "input_states",
        "input_attributes",
        "extra_input",
        "extra_options",
        "extra_attrs",
    ),
    [
        (
            "alarm_control_panel",
            {"value_template": "{{ states('alarm_control_panel.one') }}"},
            "armed_away",
            {"one": "armed_away", "two": "disarmed"},
            {},
            {},
            {"code_arm_required": True, "code_format": "number"},
            {},
        ),
        (
            "binary_sensor",
            {
                "state": "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}"
            },
            "on",
            {"one": "on", "two": "off"},
            {},
            {},
            {},
            {},
        ),
        (
            "sensor",
            {
                "state": "{{ float(states('sensor.one')) + float(states('sensor.two')) }}"
            },
            "50.0",
            {"one": "30.0", "two": "20.0"},
            {},
            {},
            {},
            {},
        ),
        (
            "button",
            {},
            "unknown",
            {"one": "30.0", "two": "20.0"},
            {},
            {
                "device_class": "restart",
                "press": [
                    {
                        "action": "input_boolean.toggle",
                        "target": {"entity_id": "input_boolean.test"},
                        "data": {},
                    }
                ],
            },
            {
                "device_class": "restart",
                "press": [
                    {
                        "action": "input_boolean.toggle",
                        "target": {"entity_id": "input_boolean.test"},
                        "data": {},
                    }
                ],
            },
            {},
        ),
        (
            "image",
            {"url": "{{ states('sensor.one') }}"},
            "2024-07-09T00:00:00+00:00",
            {"one": "http://www.test.com", "two": ""},
            {},
            {"verify_ssl": True},
            {"verify_ssl": True},
            {},
        ),
        (
            "number",
            {"state": "{{ states('number.one') }}"},
            "30.0",
            {"one": "30.0", "two": "20.0"},
            {},
            {
                "min": "0",
                "max": "100",
                "step": "0.1",
                "unit_of_measurement": "cm",
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "unit_of_measurement": "cm",
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            {},
        ),
        (
            "select",
            {"state": "{{ states('select.one') }}"},
            "on",
            {"one": "on", "two": "off"},
            {},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            {},
        ),
        (
            "switch",
            {"value_template": "{{ states('switch.one') }}"},
            "on",
            {"one": "on", "two": "off"},
            {},
            {},
            {},
            {},
        ),
    ],
)
@pytest.mark.freeze_time("2024-07-09 00:00:00+00:00")
async def test_config_flow(
    hass: HomeAssistant,
    template_type: str,
    state_template: dict[str, Any],
    template_state: str,
    input_states: dict[str, Any],
    input_attributes: dict[str, Any],
    extra_input: dict[str, Any],
    extra_options: dict[str, Any],
    extra_attrs: dict[str, Any],
) -> None:
    """Test the config flow."""
    input_entities = ["one", "two"]
    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}",
            input_states[input_entity],
            input_attributes.get(input_entity, {}),
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type

    with patch(
        "homeassistant.components.template.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My template",
                **state_template,
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My template"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My template",
        "template_type": template_type,
        **state_template,
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My template",
        "template_type": template_type,
        **state_template,
        **extra_options,
    }

    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state
    for key, value in extra_attrs.items():
        assert state.attributes[key] == value


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_input",
        "extra_options",
    ),
    [
        (
            "sensor",
            {"state": "{{ 15 }}"},
            {},
            {},
        ),
        (
            "binary_sensor",
            {"state": "{{ false }}"},
            {},
            {},
        ),
        (
            "switch",
            {"value_template": "{{ false }}"},
            {},
            {},
        ),
        (
            "button",
            {},
            {},
            {},
        ),
        (
            "image",
            {
                "url": "{{ states('sensor.one') }}",
            },
            {"verify_ssl": True},
            {"verify_ssl": True},
        ),
        (
            "number",
            {"state": "{{ states('number.one') }}"},
            {
                "min": "0",
                "max": "100",
                "step": "0.1",
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
        ),
        (
            "alarm_control_panel",
            {"value_template": "{{ states('alarm_control_panel.one') }}"},
            {"code_arm_required": True, "code_format": "number"},
            {"code_arm_required": True, "code_format": "number"},
        ),
        (
            "select",
            {"state": "{{ states('select.one') }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
        ),
    ],
)
async def test_config_flow_device(
    hass: HomeAssistant,
    template_type: str,
    state_template: dict[str, Any],
    extra_input: dict[str, Any],
    extra_options: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test remove the device registry configuration entry when the device changes."""

    # Configure a device registry
    entry_device = MockConfigEntry()
    entry_device.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_device.entry_id,
        identifiers={("test", "identifier_test1")},
        connections={("mac", "20:31:32:33:34:01")},
    )
    await hass.async_block_till_done()

    device_id = device.id
    assert device_id is not None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type

    with patch(
        "homeassistant.components.template.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My template",
                "device_id": device_id,
                **state_template,
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My template"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My template",
        "template_type": template_type,
        "device_id": device_id,
        **state_template,
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My template",
        "template_type": template_type,
        "device_id": device_id,
        **state_template,
        **extra_options,
    }


@pytest.mark.parametrize(
    (
        "template_type",
        "old_state_template",
        "new_state_template",
        "template_state",
        "input_states",
        "extra_options",
        "options_options",
        "key_template",
    ),
    [
        (
            "binary_sensor",
            {
                "state": "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}"
            },
            {
                "state": "{{ states('binary_sensor.one') == 'on' and states('binary_sensor.two') == 'on' }}"
            },
            ["on", "off"],
            {"one": "on", "two": "off"},
            {},
            {},
            "state",
        ),
        (
            "sensor",
            {
                "state": "{{ float(states('sensor.one')) + float(states('sensor.two')) }}"
            },
            {
                "state": "{{ float(states('sensor.one')) - float(states('sensor.two')) }}"
            },
            ["50.0", "10.0"],
            {"one": "30.0", "two": "20.0"},
            {},
            {},
            "state",
        ),
        (
            "button",
            {},
            {},
            ["unknown", "unknown"],
            {"one": "30.0", "two": "20.0"},
            {
                "device_class": "restart",
                "press": [
                    {
                        "action": "input_boolean.toggle",
                        "target": {"entity_id": "input_boolean.test"},
                        "data": {},
                    }
                ],
            },
            {
                "press": [
                    {
                        "action": "input_boolean.toggle",
                        "target": {"entity_id": "input_boolean.test"},
                        "data": {},
                    }
                ],
            },
            "state",
        ),
        (
            "image",
            {
                "url": "{{ states('sensor.one') }}",
            },
            {
                "url": "{{ states('sensor.two') }}",
            },
            ["2024-07-09T00:00:00+00:00", "2024-07-09T00:00:00+00:00"],
            {"one": "http://www.test.com", "two": "http://www.test2.com"},
            {"verify_ssl": True},
            {
                "url": "{{ states('sensor.two') }}",
                "verify_ssl": True,
            },
            "url",
        ),
        (
            "number",
            {"state": "{{ states('number.one') }}"},
            {"state": "{{ states('number.two') }}"},
            ["30.0", "20.0"],
            {"one": "30.0", "two": "20.0"},
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "unit_of_measurement": "cm",
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "unit_of_measurement": "cm",
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            "state",
        ),
        (
            "alarm_control_panel",
            {"value_template": "{{ states('alarm_control_panel.one') }}"},
            {"value_template": "{{ states('alarm_control_panel.two') }}"},
            ["armed_away", "disarmed"],
            {"one": "armed_away", "two": "disarmed"},
            {"code_arm_required": True, "code_format": "number"},
            {"code_arm_required": True, "code_format": "number"},
            "value_template",
        ),
        (
            "select",
            {"state": "{{ states('select.one') }}"},
            {"state": "{{ states('select.two') }}"},
            ["on", "off"],
            {"one": "on", "two": "off"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            "state",
        ),
        (
            "switch",
            {"value_template": "{{ states('switch.one') }}"},
            {"value_template": "{{ states('switch.two') }}"},
            ["on", "off"],
            {"one": "on", "two": "off"},
            {},
            {},
            "value_template",
        ),
    ],
)
@pytest.mark.freeze_time("2024-07-09 00:00:00+00:00")
async def test_options(
    hass: HomeAssistant,
    template_type: str,
    old_state_template: dict[str, Any],
    new_state_template: dict[str, Any],
    template_state: list[str],
    input_states: dict[str, Any],
    extra_options: dict[str, Any],
    options_options: dict[str, Any],
    key_template: str,
) -> None:
    """Test reconfiguring."""
    input_entities = ["one", "two"]

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "template_type": template_type,
            **old_state_template,
            **extra_options,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state[0]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert get_schema_suggested_value(
        result["data_schema"].schema, key_template
    ) == old_state_template.get(key_template)
    assert "name" not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            **new_state_template,
            **options_options,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My template",
        "template_type": template_type,
        **new_state_template,
        **extra_options,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My template",
        "template_type": template_type,
        **new_state_template,
        **extra_options,
    }
    assert config_entry.title == "My template"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state[1]

    # Check we don't get suggestions from another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type

    assert get_schema_suggested_value(result["data_schema"].schema, "name") is None
    assert (
        get_schema_suggested_value(result["data_schema"].schema, key_template) is None
    )


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_user_input",
        "input_states",
        "template_states",
        "extra_attributes",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states.binary_sensor.one.state == 'on' or states.binary_sensor.two.state == 'on' }}",
            {},
            {"one": "on", "two": "off"},
            ["off", "on"],
            [{}, {}],
            [["one", "two"], ["one"]],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one'), default='') + float(states('sensor.two'), default='') }}",
            {},
            {"one": "30.0", "two": "20.0"},
            ["", STATE_UNAVAILABLE, "50.0"],
            [{}, {}],
            [["one", "two"], ["one", "two"]],
        ),
    ],
)
async def test_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, Any],
    input_states: dict[str, Any],
    template_states: str,
    extra_attributes: list[dict[str, Any]],
    listeners: list[list[str]],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    input_entities = ["one", "two"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "My template"} | extra_attributes[0],
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners[0]]),
            "time": False,
        },
        "state": template_states[0],
    }

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )
        await hass.async_block_till_done()

    for template_state in template_states[1:]:
        msg = await client.receive_json()
        assert msg["event"] == {
            "attributes": {"friendly_name": "My template"}
            | extra_attributes[0]
            | extra_attributes[1],
            "listeners": {
                "all": False,
                "domains": [],
                "entities": unordered(
                    [f"{template_type}.{_id}" for _id in listeners[1]]
                ),
                "time": False,
            },
            "state": template_state,
        }
    assert len(hass.states.async_all()) == 2


EARLY_END_ERROR = "invalid template (TemplateSyntaxError: unexpected 'end of template')"


@pytest.mark.parametrize(
    ("template_type", "state_template", "extra_user_input", "error"),
    [
        ("binary_sensor", "{{", {}, {"state": EARLY_END_ERROR}),
        ("sensor", "{{", {}, {"state": EARLY_END_ERROR}),
        (
            "sensor",
            "",
            {"device_class": "aqi", "unit_of_measurement": "cats"},
            {
                "unit_of_measurement": (
                    "'cats' is not a valid unit for device class 'aqi'; "
                    "expected no unit of measurement"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "temperature", "unit_of_measurement": "cats"},
            {
                "unit_of_measurement": (
                    "'cats' is not a valid unit for device class 'temperature'; "
                    "expected one of 'K', '°C', '°F'"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "timestamp", "state_class": "measurement"},
            {
                "state_class": (
                    "'measurement' is not a valid state class for device class "
                    "'timestamp'; expected no state class"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "aqi", "state_class": "total"},
            {
                "state_class": (
                    "'total' is not a valid state class for device class "
                    "'aqi'; expected 'measurement'"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "energy", "state_class": "measurement"},
            {
                "state_class": (
                    "'measurement' is not a valid state class for device class "
                    "'energy'; expected one of 'total', 'total_increasing'"
                ),
                "unit_of_measurement": (
                    "'None' is not a valid unit for device class 'energy'; "
                    "expected one of 'cal', 'Gcal', 'GJ', 'GWh', 'J', 'kcal', 'kJ', 'kWh', 'Mcal', 'MJ', 'MWh', 'mWh', 'TWh', 'Wh'"
                ),
            },
        ),
    ],
)
async def test_config_flow_preview_bad_input(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, str],
    error: dict[str, str],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "invalid_user_input",
        "message": error,
    }


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "input_states",
        "template_states",
        "error_events",
    ),
    [
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            {"one": "30.0", "two": "20.0"},
            ["unavailable", "50.0"],
            [
                (
                    "ValueError: Template error: float got invalid input 'unknown' "
                    "when rendering template '{{ float(states('sensor.one')) + "
                    "float(states('sensor.two')) }}' but no default was specified"
                )
            ],
        ),
    ],
)
async def test_config_flow_preview_template_startup_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    input_states: dict[str, str],
    template_states: list[str],
    error_events: list[str],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    input_entities = ["one", "two"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template},
        }
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]

    for error_event in error_events:
        msg = await client.receive_json()
        assert msg["type"] == "event"
        assert msg["event"] == {"error": error_event}

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == template_states[0]

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == template_states[1]


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "input_states",
        "template_states",
        "error_events",
    ),
    [
        (
            "sensor",
            "{{ float(states('sensor.one')) > 30 and undefined_function() }}",
            [{"one": "30.0", "two": "20.0"}, {"one": "35.0", "two": "20.0"}],
            ["False", "unavailable"],
            ["'undefined_function' is undefined"],
        ),
    ],
)
async def test_config_flow_preview_template_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    input_states: list[dict[str, str]],
    template_states: list[str],
    error_events: list[str],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    input_entities = ["one", "two"]

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[0][input_entity], {}
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template},
        }
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == template_states[0]

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[1][input_entity], {}
        )

    for error_event in error_events:
        msg = await client.receive_json()
        assert msg["type"] == "event"
        assert msg["event"] == {"error": error_event}

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["state"] == template_states[1]


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_user_input",
    ),
    [
        (
            "sensor",
            "{{ states('sensor.one') }}",
            {"unit_of_measurement": "°C"},
        ),
    ],
)
async def test_config_flow_preview_bad_state(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, Any],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "error": (
            "Sensor None has device class 'None', state class 'None' unit '°C' "
            "and suggested precision 'None' thus indicating it has a numeric "
            "value; however, it has the non-numeric value: 'unknown' (<class "
            "'str'>)"
        ),
    }


@pytest.mark.parametrize(
    (
        "template_type",
        "old_state_template",
        "new_state_template",
        "extra_config_flow_data",
        "extra_user_input",
        "input_states",
        "template_state",
        "extra_attributes",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}",
            "{{ states('binary_sensor.one') == 'on' and states('binary_sensor.two') == 'on' }}",
            {},
            {},
            {"one": "on", "two": "off"},
            "off",
            {},
            ["one", "two"],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            "{{ float(states('sensor.one')) - float(states('sensor.two')) }}",
            {},
            {},
            {"one": "30.0", "two": "20.0"},
            "10.0",
            {},
            ["one", "two"],
        ),
    ],
)
async def test_option_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    old_state_template: str,
    new_state_template: str,
    extra_config_flow_data: dict[str, Any],
    extra_user_input: dict[str, Any],
    input_states: dict[str, Any],
    template_state: str,
    extra_attributes: dict[str, Any],
    listeners: list[str],
) -> None:
    """Test the option flow preview."""
    client = await hass_ws_client(hass)

    input_entities = ["one", "two"]

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "state": old_state_template,
            "template_type": template_type,
        }
        | extra_config_flow_data,
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {"state": new_state_template} | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "My template"} | extra_attributes,
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners]),
            "time": False,
        },
        "state": template_state,
    }
    assert len(hass.states.async_all()) == 3


async def test_option_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "state": "Hello!",
            "template_type": "sensor",
        },
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {"state": "Goodbye!"},
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {"code": "home_assistant_error", "message": "Unknown error"}


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_input",
        "extra_options",
    ),
    [
        (
            "sensor",
            {"state": "{{ 15 }}"},
            {},
            {},
        ),
        (
            "binary_sensor",
            {"state": "{{ false }}"},
            {},
            {},
        ),
        (
            "button",
            {},
            {},
            {},
        ),
        (
            "image",
            {
                "url": "{{ states('sensor.one') }}",
                "verify_ssl": True,
            },
            {},
            {},
        ),
        (
            "number",
            {"state": "{{ states('number.one') }}"},
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
            {
                "min": 0,
                "max": 100,
                "step": 0.1,
                "set_value": {
                    "action": "input_number.set_value",
                    "target": {"entity_id": "input_number.test"},
                    "data": {"value": "{{ value }}"},
                },
            },
        ),
        (
            "alarm_control_panel",
            {"value_template": "{{ states('alarm_control_panel.one') }}"},
            {"code_arm_required": True, "code_format": "number"},
            {"code_arm_required": True, "code_format": "number"},
        ),
        (
            "select",
            {"state": "{{ states('select.one') }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
            {"options": "{{ ['off', 'on', 'auto'] }}"},
        ),
        (
            "switch",
            {"value_template": "{{ false }}"},
            {},
            {},
        ),
    ],
)
async def test_options_flow_change_device(
    hass: HomeAssistant,
    template_type: str,
    state_template: dict[str, Any],
    extra_input: dict[str, Any],
    extra_options: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test remove the device registry configuration entry when the device changes."""

    # Configure a device registry
    entry_device1 = MockConfigEntry()
    entry_device1.add_to_hass(hass)
    device1 = device_registry.async_get_or_create(
        config_entry_id=entry_device1.entry_id,
        identifiers={("test", "identifier_test1")},
        connections={("mac", "20:31:32:33:34:01")},
    )
    entry_device2 = MockConfigEntry()
    entry_device2.add_to_hass(hass)
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry_device1.entry_id,
        identifiers={("test", "identifier_test2")},
        connections={("mac", "20:31:32:33:34:02")},
    )
    await hass.async_block_till_done()

    device_id1 = device1.id
    assert device_id1 is not None

    device_id2 = device2.id
    assert device_id2 is not None

    # Setup the config entry with device 1
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "template_type": template_type,
            "name": "My template",
            "device_id": device_id1,
            **state_template,
            **extra_options,
        },
        title="Template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    # Change to link to device 2
    result = await hass.config_entries.options.async_init(
        template_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "device_id": device_id2,
            **state_template,
            **extra_input,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "template_type": template_type,
        "name": "My template",
        "device_id": device_id2,
        **state_template,
        **extra_input,
    }
    assert template_config_entry.data == {}
    assert template_config_entry.options == {
        "template_type": template_type,
        "name": "My template",
        "device_id": device_id2,
        **state_template,
        **extra_options,
    }

    # Remove link with device
    result = await hass.config_entries.options.async_init(
        template_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            **state_template,
            **extra_input,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "template_type": template_type,
        "name": "My template",
        **state_template,
        **extra_input,
    }
    assert template_config_entry.data == {}
    assert template_config_entry.options == {
        "template_type": template_type,
        "name": "My template",
        **state_template,
        **extra_options,
    }

    # Change to link to device 1
    result = await hass.config_entries.options.async_init(
        template_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "device_id": device_id1,
            **state_template,
            **extra_input,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "template_type": template_type,
        "name": "My template",
        "device_id": device_id1,
        **state_template,
        **extra_input,
    }
    assert template_config_entry.data == {}
    assert template_config_entry.options == {
        "template_type": template_type,
        "name": "My template",
        "device_id": device_id1,
        **state_template,
        **extra_options,
    }
