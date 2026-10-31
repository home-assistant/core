"""Test trigger template entity."""

import asyncio
from unittest.mock import Mock, patch

import pytest
from pytest_homeassistant.common import assert_setup_component

from homeassistant.components.template import DOMAIN, trigger_entity
from homeassistant.components.template.const import TemplateService
from homeassistant.components.template.coordinator import TriggerUpdateCoordinator
from homeassistant.components.template.helpers import DATA_COORDINATORS
from homeassistant.const import (
    CONF_ICON,
    CONF_NAME,
    CONF_STATE,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import condition, config_validation as cv, template
from homeassistant.helpers.script import Script
from homeassistant.helpers.trigger_template_entity import CONF_PICTURE
from homeassistant.setup import async_setup_component

from .conftest import async_trigger

_ICON_TEMPLATE = 'mdi:o{{ "n" if value=="on" else "ff" }}'
_PICTURE_TEMPLATE = '/local/picture_o{{ "n" if value=="on" else "ff" }}'


class TestEntity(trigger_entity.TriggerEntity):
    """Test entity class."""

    domain = "test"
    __test__ = False
    _entity_id_format = "test.{}"
    extra_template_keys = (CONF_STATE,)
    _state_option = CONF_STATE

    @property
    def state(self) -> bool | None:
        """Return extra attributes."""
        return self._rendered.get(self._state_option)


async def test_reference_blueprints_is_none(hass: HomeAssistant) -> None:
    """Test template entity requires hass to be set before accepting templates."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = trigger_entity.TriggerEntity(hass, coordinator, {})

    assert entity.referenced_blueprint is None


async def test_template_state(hass: HomeAssistant) -> None:
    """Test manual trigger template entity with a state."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ value == 'on' }}", hass),
    }

    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"value": STATE_ON})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.state == "True"
    assert entity.icon == "mdi:on"
    assert entity.entity_picture == "/local/picture_on"

    coordinator._execute_update({"value": STATE_OFF})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.state == "False"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"


async def test_validator_error_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid results clear the attribute without preventing later updates."""
    config = {
        CONF_ICON: template.Template("{{ icon }}", hass),
        CONF_STATE: template.Template("{{ value }}", hass),
    }
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"
    entity.setup_template(CONF_ICON, "_attr_icon", cv.icon)

    coordinator._execute_update({"icon": "mdi:home", "value": "first"})
    entity._handle_coordinator_update()
    assert entity._attr_icon == "mdi:home"

    coordinator._execute_update({"icon": "invalid", "value": "second"})
    entity._handle_coordinator_update()
    assert entity._attr_icon is None
    assert hass.states.get("test.entity").state == "second"
    assert "Error validating template result 'invalid'" in caplog.text
    assert "for attribute '_attr_icon' in entity test.entity" in caplog.text

    coordinator._execute_update({"icon": "mdi:lightbulb", "value": "third"})
    entity._handle_coordinator_update()
    assert entity._attr_icon == "mdi:lightbulb"
    assert hass.states.get("test.entity").state == "third"


async def test_validator_error_callback(hass: HomeAssistant) -> None:
    """Pass None to the update callback on validation failure and recover."""
    config = {
        CONF_ICON: template.Template("{{ icon }}", hass),
        CONF_STATE: template.Template("on", hass),
    }
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"
    on_update = Mock()
    entity.setup_template(CONF_ICON, "_attr_icon", cv.icon, on_update)

    coordinator._execute_update({"icon": "invalid"})
    entity._handle_coordinator_update()
    on_update.assert_called_once_with(None)

    on_update.reset_mock()
    coordinator._execute_update({"icon": "mdi:home"})
    entity._handle_coordinator_update()
    on_update.assert_called_once_with("mdi:home")


async def test_bad_template_state(hass: HomeAssistant) -> None:
    """Test manual trigger template entity with a state."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ x - 1 }}", hass),
    }
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"x": 1})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.available is True
    assert entity.state == "0"
    assert entity.icon == "mdi:off"
    assert entity.entity_picture == "/local/picture_off"

    coordinator._execute_update({"value": STATE_OFF})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert entity.available is False
    assert entity.state is None
    assert entity.icon is None
    assert entity.entity_picture is None


async def test_template_state_syntax_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test manual trigger template entity when state render fails."""
    config = {
        CONF_NAME: template.Template("test_entity", hass),
        CONF_ICON: template.Template(_ICON_TEMPLATE, hass),
        CONF_PICTURE: template.Template(_PICTURE_TEMPLATE, hass),
        CONF_STATE: template.Template("{{ incorrect ", hass),
    }

    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, config)
    entity.entity_id = "test.entity"

    coordinator._execute_update({"value": STATE_ON})
    entity._handle_coordinator_update()
    await hass.async_block_till_done()

    assert f"Error rendering {CONF_STATE} template for test.entity" in caplog.text

    assert entity.state is None
    assert entity.icon is None
    assert entity.entity_picture is None


async def test_script_variables_from_coordinator(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test script variables."""
    await async_trigger(hass, "sensor.start", "1")
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "variables": {"a": "{{ states('sensor.start') }}", "c": 0},
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger"],
                    },
                    "actions": [
                        {
                            "action": "test.automation",
                            "data": {
                                "a": "{{ a }}",
                                "b": "{{ b }}",
                                "c": "{{ c }}",
                            },
                        }
                    ],
                    "sensor": {
                        "name": "test",
                        "state": "{{ 'on' }}",
                        "variables": {"b": "{{ a + 1 }}", "c": 1},
                        "attributes": {
                            "a": "{{ a }}",
                            "b": "{{ b }}",
                            "c": "{{ c }}",
                        },
                    },
                },
            },
        )
    await async_trigger(hass, "sensor.trigger", "anything")

    assert len(calls) == 1
    assert calls[0].data["a"] == 1
    assert calls[0].data["c"] == 0
    assert "'b' is undefined when rendering '{{ b }}'" in caplog.text

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == "on"
    assert state.attributes["a"] == 1
    assert state.attributes["b"] == 2
    assert state.attributes["c"] == 1


async def test_trigger_variables(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test trigger variables are available to triggers, actions and entities."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": {
                        "event_prefix": "my",
                        "a": "defined_in_trigger_variables",
                        "b": "defined_in_trigger_variables",
                    },
                    "variables": {
                        "b": "overridden_in_variables",
                        "c": "{{ a }}_in_variables",
                    },
                    "triggers": {
                        "trigger": "event",
                        "event_type": "{{ event_prefix }}_event",
                    },
                    "actions": [
                        {
                            "action": "test.automation",
                            "data": {"a": "{{ a }}", "b": "{{ b }}", "c": "{{ c }}"},
                        }
                    ],
                    "sensor": {
                        "name": "test",
                        "state": "{{ trigger.event.event_type }}",
                        "attributes": {"a": "{{ a }}", "b": "{{ b }}", "c": "{{ c }}"},
                    },
                },
            },
        )
    await hass.async_block_till_done()

    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["a"] == "defined_in_trigger_variables"
    assert calls[0].data["b"] == "overridden_in_variables"
    assert calls[0].data["c"] == "defined_in_trigger_variables_in_variables"

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == "my_event"
    assert state.attributes["a"] == "defined_in_trigger_variables"
    assert state.attributes["b"] == "overridden_in_variables"
    assert state.attributes["c"] == "defined_in_trigger_variables_in_variables"
    assert "Error rendering trigger variables" not in caplog.text


async def test_trigger_variables_passed_to_entity_actions(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test trigger variables are passed to entity action scripts."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": {"a": "trigger_variable", "b": "{{ a }}_b"},
                    "variables": {"b": "overridden_in_variables"},
                    "triggers": {"trigger": "event", "event_type": "my_event"},
                    "switch": {
                        "name": "test",
                        "state": "{{ true }}",
                        "turn_on": {
                            "action": "test.automation",
                            "data": {"a": "{{ a }}", "b": "{{ b }}"},
                        },
                        "turn_off": [],
                    },
                },
            },
        )
    await hass.async_block_till_done()

    # Trigger variables are available before the trigger fires.
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    assert len(calls) == 1
    assert calls[0].data == {"a": "trigger_variable", "b": "trigger_variable_b"}

    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    assert len(calls) == 2
    assert calls[1].data == {"a": "trigger_variable", "b": "overridden_in_variables"}


async def test_entity_action_variables_override_trigger_variables(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test variables passed to an entity action override trigger variables."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": {"brightness": 1},
                    "variables": {"brightness": 2},
                    "triggers": {"trigger": "event", "event_type": "my_event"},
                    "light": {
                        "name": "test",
                        "state": "{{ true }}",
                        "level": "{{ 100 }}",
                        "turn_on": [],
                        "turn_off": [],
                        "set_level": {
                            "action": "test.automation",
                            "data": {"brightness": "{{ brightness }}"},
                        },
                    },
                },
            },
        )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", "brightness": 200},
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data["brightness"] == 200

    # The variables section is rendered once the trigger fires.
    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", "brightness": 150},
        blocking=True,
    )
    assert len(calls) == 2
    assert calls[1].data["brightness"] == 150


@pytest.mark.parametrize(
    "trigger_variables",
    [
        pytest.param({}, id="without_trigger_variables"),
        pytest.param(
            {"trigger": {"id": "trigger_variable"}}, id="with_trigger_variables"
        ),
    ],
)
async def test_variables_cannot_shadow_trigger_data(
    hass: HomeAssistant, trigger_variables: dict
) -> None:
    """Test variables that collide with trigger data do not affect later variables."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": trigger_variables,
                    "variables": {
                        "trigger": {"id": "shadow"},
                        "observed": "{{ trigger.id }}",
                    },
                    "triggers": {
                        "trigger": "event",
                        "event_type": "my_event",
                        "id": "real",
                    },
                    "sensor": {"name": "test", "state": "{{ observed }}"},
                },
            },
        )
    await hass.async_block_till_done()

    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test").state == "real"


@pytest.mark.parametrize(
    ("variables", "expected"),
    [
        pytest.param(
            {"base": "{{ base + 1 }}", "observed": "{{ base }}"},
            "11",
            id="override_references_trigger_variable",
        ),
        pytest.param(
            {"observed": "{{ base }}", "base": 20},
            "10",
            id="earlier_variable_references_overridden_trigger_variable",
        ),
    ],
)
async def test_variables_reference_trigger_variables(
    hass: HomeAssistant,
    variables: dict,
    expected: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test variables can reference trigger variables they override."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": {"base": 10},
                    "variables": variables,
                    "triggers": {"trigger": "event", "event_type": "my_event"},
                    "sensor": {"name": "test", "state": "{{ observed }}"},
                },
            },
        )
    await hass.async_block_till_done()

    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test").state == expected
    assert "TemplateError" not in caplog.text


async def test_trigger_variables_rendered_on_reload(hass: HomeAssistant) -> None:
    """Test trigger variables are rendered when the configuration is reloaded."""

    def _config(event_prefix: str) -> dict:
        return {
            "template": {
                "trigger_variables": {"event_prefix": event_prefix},
                "triggers": {
                    "trigger": "event",
                    "event_type": "{{ event_prefix }}_event",
                },
                "sensor": {"name": "test", "state": "{{ event_prefix }}"},
            }
        }

    assert await async_setup_component(hass, DOMAIN, _config("first"))
    await hass.async_block_till_done()

    hass.bus.async_fire("first_event")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test").state == "first"

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=_config("second"),
    ):
        await hass.services.async_call(DOMAIN, TemplateService.RELOAD, blocking=True)
        await hass.async_block_till_done()

    listeners = hass.bus.async_listeners()
    assert listeners.get("first_event", 0) == 0
    assert listeners.get("second_event", 0) == 1

    hass.bus.async_fire("second_event")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test").state == "second"


async def test_bad_trigger_variables(
    hass: HomeAssistant, calls: list[ServiceCall], caplog: pytest.LogCaptureFixture
) -> None:
    """Test trigger variables accessing hass are rejected."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "trigger_variables": {"a": "{{ states('sensor.foo') }}"},
                    "triggers": {"trigger": "event", "event_type": "my_event"},
                    "actions": [{"action": "test.automation"}],
                    "sensor": {"name": "test", "state": "{{ 'on' }}"},
                },
            },
        )
    await hass.async_block_till_done()

    assert "Error rendering trigger variables" in caplog.text
    assert "Use of 'states' is not supported in limited templates" in caplog.text

    hass.bus.async_fire("my_event")
    await hass.async_block_till_done()

    assert len(calls) == 0
    state = hass.states.get("sensor.test")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, {"default_entity_id": "test.test"})
    assert entity.entity_id == "test.test"


async def test_bad_default_entity_id(hass: HomeAssistant) -> None:
    """Test template entity creates suggested entity_id from the default_entity_id."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = TestEntity(hass, coordinator, {"default_entity_id": "bad.test"})
    assert entity.entity_id == "test.test"


async def test_multiple_template_validators(hass: HomeAssistant) -> None:
    """Tests multiple templates execute validators."""
    await async_trigger(hass, "sensor.state", "opening")
    await async_trigger(hass, "sensor.position", "50")
    await async_trigger(hass, "sensor.tilt", "49")
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger"],
                    },
                    "cover": {
                        "name": "test",
                        "state": "{{ states('sensor.state') }}",
                        "position": "{{ states('sensor.position') }}",
                        "tilt": "{{ states('sensor.tilt') }}",
                        "set_cover_position": [],
                        "set_cover_tilt_position": [],
                        "open_cover": [],
                        "close_cover": [],
                    },
                },
            },
        )
    await async_trigger(hass, "sensor.trigger", "anything")

    state = hass.states.get("cover.test")
    assert state
    assert state.state == "opening"
    assert state.attributes["current_position"] == 50
    assert state.attributes["current_tilt_position"] == 49


async def test_coordinator_shutdown_unloads_script_and_condition(
    hass: HomeAssistant,
) -> None:
    """Test that coordinator shutdown stops and unloads script and condition."""
    coordinator = TriggerUpdateCoordinator(hass, {})

    mock_script = Mock(spec=Script)
    mock_cond = Mock(spec=condition.ConditionsChecker)
    coordinator._script = mock_script
    coordinator._cond_func = mock_cond

    await coordinator.async_shutdown()

    mock_script.async_unload.assert_called_once()
    mock_cond.async_unload.assert_called_once()


async def test_shutdown_stops_script_and_keeps_triggers_subscribed(
    hass: HomeAssistant,
) -> None:
    """Test HA shutdown stops coordinator scripts without unsubscribing."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": [
                    {"event": "action_event"},
                    {"delay": {"seconds": 120}},
                ],
                "sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.data.value }}",
                },
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Verify trigger is active
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event", 0) == 1

    # Fire the trigger to start the action script, then yield without
    # waiting for the script to finish
    hass.bus.async_fire("test_event", {"value": "hello"})
    await asyncio.sleep(0)

    # Script should be running (stuck on delay)
    coordinators = hass.data[DATA_COORDINATORS]
    assert len(coordinators) == 1
    assert coordinators[0]._script.is_running
    assert not coordinators[0]._script._unloaded

    # Fire shutdown
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Script should be stopped but not unloaded - this is handled by the script helper
    assert not coordinators[0]._script.is_running
    assert not coordinators[0]._script._unloaded

    # Triggers are not unsubscribed on shutdown
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event", 0) == 1


async def test_reload_stops_script_and_unsubscribes_triggers(
    hass: HomeAssistant,
) -> None:
    """Test that reloading stops coordinator scripts and unsubscribes old triggers."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": [
                    {"event": "action_event"},
                    {"delay": {"seconds": 120}},
                ],
                "sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.data.value }}",
                },
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Verify trigger is active
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event", 0) == 1

    # Fire the trigger to start the action script
    hass.bus.async_fire("test_event", {"value": "hello"})
    await asyncio.sleep(0)

    # Script should be running
    coordinators = hass.data[DATA_COORDINATORS]
    assert len(coordinators) == 1
    coordinator = coordinators[0]
    assert coordinator._script.is_running
    assert not coordinator._script._unloaded

    # Reload with empty config
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={"template": []},
    ):
        await hass.services.async_call(DOMAIN, TemplateService.RELOAD, blocking=True)
        await hass.async_block_till_done()

    # Script should be stopped and unloaded
    assert not coordinator._script.is_running
    assert coordinator._script._unloaded

    # Old trigger should be unsubscribed
    listeners = hass.bus.async_listeners()
    assert listeners.get("test_event", 0) == 0


async def test_entity_conditions_with_multiple_entities(hass: HomeAssistant) -> None:
    """Test entity conditions with multiple entities."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger"],
                    },
                    "sensor": [
                        {
                            "name": "a",
                            "state": "{{ states('sensor.trigger') }}",
                            "conditions": {
                                "condition": "numeric_state",
                                "entity_id": "sensor.trigger",
                                "above": 1,
                            },
                        },
                        {
                            "name": "b",
                            "state": "{{ trigger.to_state.state }}",
                            "conditions": {
                                "condition": "numeric_state",
                                "entity_id": "sensor.trigger",
                                "below": 1,
                            },
                        },
                    ],
                },
            },
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.a")
    assert state
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("sensor.b")
    assert state
    assert state.state == STATE_UNKNOWN

    await async_trigger(hass, "sensor.trigger", "2")

    state = hass.states.get("sensor.a")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.b")
    assert state
    assert state.state == STATE_UNKNOWN

    await async_trigger(hass, "sensor.trigger", "0")

    state = hass.states.get("sensor.a")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.b")
    assert state
    assert state.state == "0"


async def test_entity_conditions_variables(hass: HomeAssistant) -> None:
    """Test entity conditions variables."""
    await async_trigger(hass, "sensor.start", "0")
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                "template": {
                    "triggers": {
                        "trigger": "state",
                        "entity_id": ["sensor.trigger", "sensor.start"],
                    },
                    "variables": {"a": "{{ states('sensor.start') }}"},
                    "sensor": [
                        {
                            "name": "test",
                            "state": "{{ states('sensor.start') }}",
                            "variables": {"b": "{{ a + 1 }}"},
                            "conditions": {
                                "condition": "template",
                                "value_template": "{{ b > 1 }}",
                            },
                            "attributes": {
                                "a": "{{ a }}",
                                "b": "{{ b }}",
                            },
                        },
                    ],
                },
            },
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == STATE_UNKNOWN
    assert "a" not in state.attributes
    assert "b" not in state.attributes

    await async_trigger(hass, "sensor.trigger", "anything")

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == STATE_UNKNOWN
    assert "a" not in state.attributes
    assert "b" not in state.attributes

    await async_trigger(hass, "sensor.start", "1")

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == "1"
    assert state.attributes["a"] == 1
    assert state.attributes["b"] == 2

    await async_trigger(hass, "sensor.start", "0")

    state = hass.states.get("sensor.test")
    assert state
    assert state.state == "1"
    assert state.attributes["a"] == 1
    assert state.attributes["b"] == 2


async def test_entity_remove_unloads_condition(
    hass: HomeAssistant,
) -> None:
    """Test that removing the entity unloads the condition."""
    coordinator = TriggerUpdateCoordinator(hass, {})

    mock_cond = Mock(spec=condition.ConditionsChecker)

    entity = TestEntity(hass, coordinator, {})
    entity._cond_func = mock_cond
    await entity.async_will_remove_from_hass()

    mock_cond.async_unload.assert_called_once()
