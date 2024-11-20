"""The tests for the Script component."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.components import script
from homeassistant.components.script import DOMAIN, EVENT_SCRIPT_STARTED, ScriptEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    Context,
    CoreState,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import ServiceNotFound, TemplateError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import (
    SCRIPT_MODE_CHOICES,
    SCRIPT_MODE_PARALLEL,
    SCRIPT_MODE_QUEUED,
    SCRIPT_MODE_RESTART,
    SCRIPT_MODE_SINGLE,
    _async_stop_scripts_at_shutdown,
)
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockUser,
    async_fire_time_changed,
    async_mock_service,
    mock_restore_cache,
)
from tests.components.logbook.common import MockRow, mock_humanify
from tests.components.repairs import get_repairs
from tests.typing import WebSocketGenerator

ENTITY_ID = "script.test"


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "script")


async def test_passing_variables(hass: HomeAssistant) -> None:
    """Test different ways of passing in variables."""
    mock_restore_cache(hass, ())
    calls = []
    context = Context()

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": {
                        "action": "test.script",
                        "data_template": {"hello": "{{ greeting }}"},
                    }
                }
            }
        },
    )

    await hass.services.async_call(
        DOMAIN, "test", {"greeting": "world"}, context=context
    )

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data["hello"] == "world"

    await hass.services.async_call(
        "script", "test", {"greeting": "universe"}, context=context
    )

    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[1].context is context
    assert calls[1].data["hello"] == "universe"


@pytest.mark.parametrize("toggle", [False, True])
@pytest.mark.parametrize("action_schema_variations", ["action", "service"])
async def test_turn_on_off_toggle(
    hass: HomeAssistant, toggle: bool, action_schema_variations: str
) -> None:
    """Verify turn_on, turn_off & toggle services.

    Ensures backward compatibility with the old service action schema is maintained.
    """
    event = "test_event"
    event_mock = Mock()

    hass.bus.async_listen(event, event_mock)

    was_on = False

    @callback
    def state_listener(entity_id, old_state, new_state):
        nonlocal was_on
        was_on = True

    async_track_state_change(hass, ENTITY_ID, state_listener, to_state="on")

    if toggle:
        turn_off_step = {
            action_schema_variations: "script.toggle",
            "entity_id": ENTITY_ID,
        }
    else:
        turn_off_step = {
            action_schema_variations: "script.turn_off",
            "entity_id": ENTITY_ID,
        }
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": [{"event": event}, turn_off_step, {"event": event}]
                }
            }
        },
    )

    assert not script.is_on(hass, ENTITY_ID)

    if toggle:
        await hass.services.async_call(
            DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_ID}
        )
    else:
        await hass.services.async_call(DOMAIN, split_entity_id(ENTITY_ID)[1])
    await hass.async_block_till_done()

    assert not script.is_on(hass, ENTITY_ID)
    assert was_on
    assert event_mock.call_count == 1


invalid_configs = [
    {"test": {}},
    {"test hello world": {"sequence": [{"event": "bla"}]}},
    {"test": {"sequence": {"event": "test_event", "action": "homeassistant.turn_on"}}},
]


@pytest.mark.parametrize(
    ("config", "nbr_script_entities"),
    [
        ({"test": {}}, 1),
        # Invalid slug, entity can't be set up
        ({"test hello world": {"sequence": [{"event": "bla"}]}}, 0),
        (
            {
                "test": {
                    "sequence": {
                        "event": "test_event",
                        "action": "homeassistant.turn_on",
                    }
                }
            },
            1,
        ),
    ],
)
async def test_setup_with_invalid_configs(
    hass: HomeAssistant, config, nbr_script_entities
) -> None:
    """Test setup with invalid configs."""
    assert await async_setup_component(hass, "script", {"script": config})

    assert len(hass.states.async_entity_ids("script")) == nbr_script_entities


@pytest.mark.parametrize(
    ("object_id", "broken_config", "problem", "details"),
    [
        (
            "Bad Script",
            {},
            "has invalid object id",
            "invalid slug Bad Script",
        ),
        (
            "turn_on",
            {},
            "has invalid object id",
            (
                "A script's object_id must not be one of "
                "reload, toggle, turn_off, turn_on. Got 'turn_on'"
            ),
        ),
    ],
)
async def test_bad_config_validation_critical(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    object_id,
    broken_config,
    problem,
    details,
) -> None:
    """Test bad script configuration which can be detected during validation."""
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                object_id: {"alias": "bad_script", **broken_config},
                "good_script": {
                    "alias": "good_script",
                    "sequence": {
                        "action": "test.automation",
                        "entity_id": "hello.world",
                    },
                },
            }
        },
    )

    # Check we get the expected error message
    assert (
        f"Script with alias 'bad_script' {problem} and has been disabled: {details}"
        in caplog.text
    )

    # Make sure one bad script does not prevent other scripts from setting up
    assert hass.states.async_entity_ids("script") == ["script.good_script"]


@pytest.mark.parametrize(
    ("object_id", "broken_config", "problem", "details", "issue"),
    [
        (
            "bad_script",
            {},
            "could not be validated",
            "required key not provided @ data['sequence']",
            "validation_failed_schema",
        ),
        (
            "bad_script",
            {
                "sequence": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                },
            },
            "failed to setup sequence",
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd.",
            "validation_failed_sequence",
        ),
    ],
)
async def test_bad_config_validation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    hass_admin_user: MockUser,
    object_id,
    broken_config,
    problem,
    details,
    issue,
) -> None:
    """Test bad script configuration which can be detected during validation."""
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                object_id: {"alias": "bad_script", **broken_config},
                "good_script": {
                    "alias": "good_script",
                    "sequence": {
                        "action": "test.automation",
                        "entity_id": "hello.world",
                    },
                },
            }
        },
    )

    # Check we get the expected error message and issue
    assert (
        f"Script with alias 'bad_script' {problem} and has been disabled: {details}"
        in caplog.text
    )
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == f"script.bad_script_{issue}"
    assert issues[0]["translation_key"] == issue
    assert issues[0]["translation_placeholders"] == {
        "edit": "/config/script/edit/bad_script",
        "entity_id": "script.bad_script",
        "error": ANY,
        "name": "bad_script",
    }
    assert issues[0]["translation_placeholders"]["error"].startswith(details)

    # Make sure both scripts are setup
    assert set(hass.states.async_entity_ids("script")) == {
        "script.bad_script",
        "script.good_script",
    }
    # The script failing validation should be unavailable
    assert hass.states.get("script.bad_script").state == STATE_UNAVAILABLE

    # Reloading the automation with fixed config should clear the issue
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            script.DOMAIN: {
                object_id: {
                    "alias": "bad_script",
                    "sequence": {
                        "action": "test.automation",
                        "entity_id": "hello.world",
                    },
                },
            }
        },
    ):
        await hass.services.async_call(
            script.DOMAIN,
            SERVICE_RELOAD,
            context=Context(user_id=hass_admin_user.id),
            blocking=True,
        )
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 0


@pytest.mark.parametrize("running", ["no", "same", "different"])
async def test_reload_service(hass: HomeAssistant, running) -> None:
    """Verify the reload service."""
    event = "test_event"
    event_flag = asyncio.Event()

    @callback
    def event_handler(event):
        event_flag.set()

    hass.bus.async_listen_once(event, event_handler)
    hass.states.async_set("test.script", "off")

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": [
                        {"event": event},
                        {"wait_template": "{{ is_state('test.script', 'on') }}"},
                    ]
                }
            }
        },
    )

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.services.has_service(script.DOMAIN, "test")

    if running != "no":
        _, object_id = split_entity_id(ENTITY_ID)
        await hass.services.async_call(DOMAIN, object_id)
        await asyncio.wait_for(event_flag.wait(), 1)

        assert script.is_on(hass, ENTITY_ID)

    object_id = "test" if running == "same" else "test2"
    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"script": {object_id: {"sequence": [{"delay": {"seconds": 5}}]}}},
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    if running != "same":
        state = hass.states.get(ENTITY_ID)
        assert state.attributes["restored"] is True
        assert not hass.services.has_service(script.DOMAIN, "test")

        assert hass.states.get("script.test2") is not None
        assert hass.services.has_service(script.DOMAIN, "test2")

    else:
        assert hass.states.get(ENTITY_ID) is not None
        assert hass.services.has_service(script.DOMAIN, "test")


async def test_reload_unchanged_does_not_stop(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test that reloading stops any running actions as appropriate."""
    test_entity = "test.entity"

    config = {
        script.DOMAIN: {
            "test": {
                "sequence": [
                    {"event": "running"},
                    {"wait_template": "{{ is_state('test.entity', 'goodbye') }}"},
                    {"action": "test.script"},
                ],
            }
        }
    }
    assert await async_setup_component(hass, script.DOMAIN, config)

    assert hass.states.get(ENTITY_ID) is not None
    assert hass.services.has_service(script.DOMAIN, "test")

    running = asyncio.Event()

    @callback
    def running_cb(event):
        running.set()

    hass.bus.async_listen_once("running", running_cb)
    hass.states.async_set(test_entity, "hello")

    # Start the script and wait for it to start
    _, object_id = split_entity_id(ENTITY_ID)
    await hass.services.async_call(DOMAIN, object_id)
    await running.wait()
    assert len(calls) == 0

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(script.DOMAIN, SERVICE_RELOAD, blocking=True)

    hass.states.async_set(test_entity, "goodbye")
    await hass.async_block_till_done()

    assert len(calls) == 1


@pytest.mark.parametrize(
    "script_config",
    [
        {
            "test": {
                "sequence": [{"action": "test.script"}],
            }
        },
        # A script using templates
        {
            "test": {
                "sequence": [{"action": "{{ 'test.script' }}"}],
            }
        },
        # A script using blueprint
        {
            "test": {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {
                        "service_to_call": "test.script",
                    },
                }
            }
        },
        # A script using blueprint with templated input
        {
            "test": {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {
                        "service_to_call": "{{ 'test.script' }}",
                    },
                }
            }
        },
    ],
)
async def test_reload_unchanged_script(
    hass: HomeAssistant, calls: list[ServiceCall], script_config
) -> None:
    """Test an unmodified script is not reloaded."""
    with patch(
        "homeassistant.components.script.ScriptEntity", wraps=ScriptEntity
    ) as script_entity_init:
        config = {script.DOMAIN: [script_config]}
        assert await async_setup_component(hass, script.DOMAIN, config)
        assert hass.states.get(ENTITY_ID) is not None
        assert hass.services.has_service(script.DOMAIN, "test")

        assert script_entity_init.call_count == 1
        script_entity_init.reset_mock()

        # Start the script and wait for it to finish
        _, object_id = split_entity_id(ENTITY_ID)
        await hass.services.async_call(DOMAIN, object_id)
        await hass.async_block_till_done()
        assert len(calls) == 1

        # Reload the scripts without any change
        with patch(
            "homeassistant.config.load_yaml_config_file",
            autospec=True,
            return_value=config,
        ):
            await hass.services.async_call(script.DOMAIN, SERVICE_RELOAD, blocking=True)

        assert script_entity_init.call_count == 0
        script_entity_init.reset_mock()

        # Start the script and wait for it to start
        _, object_id = split_entity_id(ENTITY_ID)
        await hass.services.async_call(DOMAIN, object_id)
        await hass.async_block_till_done()
        assert len(calls) == 2


async def test_service_descriptions(hass: HomeAssistant) -> None:
    """Test that service descriptions are loaded and reloaded correctly."""
    # Test 1: has "description" but no "fields"
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "description": "test description",
                    "sequence": [{"delay": {"seconds": 5}}],
                }
            }
        },
    )

    descriptions = await async_get_all_descriptions(hass)

    assert descriptions[DOMAIN]["test"]["name"] == "test"
    assert descriptions[DOMAIN]["test"]["description"] == "test description"
    assert not descriptions[DOMAIN]["test"]["fields"]

    # Test 2: has "fields" but no "description"
    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={
            "script": {
                "test": {
                    "fields": {
                        "test_param": {
                            "description": "test_param description",
                            "example": "test_param example",
                        }
                    },
                    "sequence": [{"delay": {"seconds": 5}}],
                }
            }
        },
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    descriptions = await async_get_all_descriptions(hass)

    assert descriptions[script.DOMAIN]["test"]["description"] == ""
    assert (
        descriptions[script.DOMAIN]["test"]["fields"]["test_param"]["description"]
        == "test_param description"
    )
    assert (
        descriptions[script.DOMAIN]["test"]["fields"]["test_param"]["example"]
        == "test_param example"
    )

    # Test 3: has "alias" that will be used as "name"
    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={
            "script": {
                "test_name": {
                    "alias": "ABC",
                    "sequence": [{"delay": {"seconds": 5}}],
                }
            }
        },
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    descriptions = await async_get_all_descriptions(hass)

    assert descriptions[DOMAIN]["test_name"]["name"] == "ABC"

    # Test 4: verify that names from YAML are taken into account as well
    assert descriptions[DOMAIN]["turn_on"]["name"] == "Turn on"


async def test_shared_context(hass: HomeAssistant) -> None:
    """Test that the shared context is passed down the chain."""
    event = "test_event"
    context = Context()

    event_mock = Mock()
    run_mock = Mock()

    hass.bus.async_listen(event, event_mock)
    hass.bus.async_listen(EVENT_SCRIPT_STARTED, run_mock)

    assert await async_setup_component(
        hass, "script", {"script": {"test": {"sequence": [{"event": event}]}}}
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, context=context
    )
    await hass.async_block_till_done()

    assert event_mock.call_count == 1
    assert run_mock.call_count == 1

    args, kwargs = run_mock.call_args
    assert args[0].context == context
    # Ensure event data has all attributes set
    assert args[0].data.get(ATTR_NAME) == "test"
    assert args[0].data.get(ATTR_ENTITY_ID) == "script.test"

    # Ensure context carries through the event
    args, kwargs = event_mock.call_args
    assert args[0].context == context

    # Ensure the script state shares the same context
    state = hass.states.get("script.test")
    assert state is not None
    assert state.context == context


async def test_logging_script_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test logging script error."""
    assert await async_setup_component(
        hass,
        "script",
        {"script": {"hello": {"sequence": [{"action": "non.existing"}]}}},
    )
    with pytest.raises(ServiceNotFound) as err:
        await hass.services.async_call("script", "hello", blocking=True)

    assert err.value.domain == "non"
    assert err.value.service == "existing"
    assert "Error executing script" in caplog.text


async def test_turning_no_scripts_off(hass: HomeAssistant) -> None:
    """Test it is possible to turn two scripts off."""
    assert await async_setup_component(hass, "script", {})

    # Testing it doesn't raise
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {"entity_id": []}, blocking=True
    )


async def test_async_get_descriptions_script(hass: HomeAssistant) -> None:
    """Test async_set_service_schema for the script integration."""
    script_config = {
        DOMAIN: {
            "test1": {"sequence": [{"action": "homeassistant.restart"}]},
            "test2": {
                "description": "test2",
                "fields": {
                    "param": {
                        "description": "param_description",
                        "example": "param_example",
                    }
                },
                "sequence": [{"action": "homeassistant.restart"}],
            },
        }
    }

    await async_setup_component(hass, DOMAIN, script_config)
    descriptions = await async_get_all_descriptions(hass)

    assert descriptions[DOMAIN]["test1"]["description"] == ""
    assert not descriptions[DOMAIN]["test1"]["fields"]

    assert descriptions[DOMAIN]["test2"]["description"] == "test2"
    assert (
        descriptions[DOMAIN]["test2"]["fields"]["param"]["description"]
        == "param_description"
    )
    assert (
        descriptions[DOMAIN]["test2"]["fields"]["param"]["example"] == "param_example"
    )


async def test_extraction_functions_not_setup(hass: HomeAssistant) -> None:
    """Test extraction functions when script is not setup."""
    assert script.scripts_with_area(hass, "area-in-both") == []
    assert script.areas_in_script(hass, "script.test") == []
    assert script.scripts_with_blueprint(hass, "blabla.yaml") == []
    assert script.blueprint_in_script(hass, "script.test") is None
    assert script.scripts_with_device(hass, "device-in-both") == []
    assert script.devices_in_script(hass, "script.test") == []
    assert script.scripts_with_entity(hass, "light.in_both") == []
    assert script.entities_in_script(hass, "script.test") == []
    assert script.scripts_with_floor(hass, "floor-in-both") == []
    assert script.floors_in_script(hass, "script.test") == []
    assert script.scripts_with_label(hass, "label-in-both") == []
    assert script.labels_in_script(hass, "script.test") == []


async def test_extraction_functions_unknown_script(hass: HomeAssistant) -> None:
    """Test extraction functions for an unknown script."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert script.labels_in_script(hass, "script.unknown") == []
    assert script.floors_in_script(hass, "script.unknown") == []
    assert script.areas_in_script(hass, "script.unknown") == []
    assert script.blueprint_in_script(hass, "script.unknown") is None
    assert script.devices_in_script(hass, "script.unknown") == []
    assert script.entities_in_script(hass, "script.unknown") == []


async def test_extraction_functions_unavailable_script(hass: HomeAssistant) -> None:
    """Test extraction functions for an unknown automation."""
    entity_id = "script.test1"
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test1": {}}},
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert script.scripts_with_area(hass, "area-in-both") == []
    assert script.areas_in_script(hass, entity_id) == []
    assert script.scripts_with_blueprint(hass, "blabla.yaml") == []
    assert script.blueprint_in_script(hass, entity_id) is None
    assert script.scripts_with_device(hass, "device-in-both") == []
    assert script.devices_in_script(hass, entity_id) == []
    assert script.scripts_with_entity(hass, "light.in_both") == []
    assert script.entities_in_script(hass, entity_id) == []
    assert script.scripts_with_floor(hass, "floor-in-both") == []
    assert script.floors_in_script(hass, entity_id) == []
    assert script.scripts_with_label(hass, "label-in-both") == []
    assert script.labels_in_script(hass, entity_id) == []


async def test_extraction_functions(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test extraction functions."""
    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    config_entry.add_to_hass(hass)

    device_in_both = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:02")},
    )
    device_in_last = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:03")},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test1": {
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "action": "test.script",
                            "data": {"entity_id": "light.in_first"},
                        },
                        {
                            "entity_id": "light.device_in_both",
                            "domain": "light",
                            "type": "turn_on",
                            "device_id": device_in_both.id,
                        },
                        {
                            "action": "test.test",
                            "target": {"area_id": "area-in-both"},
                        },
                        {
                            "action": "test.test",
                            "target": {"floor_id": "floor-in-both"},
                        },
                        {
                            "action": "test.test",
                            "target": {"label_id": "label-in-both"},
                        },
                    ]
                },
                "test2": {
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "condition": "state",
                            "entity_id": "sensor.condition",
                            "state": "100",
                        },
                        {"scene": "scene.hello"},
                        {
                            "entity_id": "light.device_in_both",
                            "domain": "light",
                            "type": "turn_on",
                            "device_id": device_in_both.id,
                        },
                        {
                            "entity_id": "light.device_in_last",
                            "domain": "light",
                            "type": "turn_on",
                            "device_id": device_in_last.id,
                        },
                    ],
                },
                "test3": {
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {"entity_id": "light.in_both"},
                        },
                        {
                            "condition": "state",
                            "entity_id": "sensor.condition",
                            "state": "100",
                        },
                        {"scene": "scene.hello"},
                        {
                            "action": "test.test",
                            "target": {"area_id": "area-in-both"},
                        },
                        {
                            "action": "test.test",
                            "target": {"area_id": "area-in-last"},
                        },
                        {
                            "action": "test.test",
                            "target": {"floor_id": "floor-in-both"},
                        },
                        {
                            "action": "test.test",
                            "target": {"floor_id": "floor-in-last"},
                        },
                        {
                            "action": "test.test",
                            "target": {"label_id": "label-in-both"},
                        },
                        {
                            "action": "test.test",
                            "target": {"label_id": "label-in-last"},
                        },
                    ],
                },
            }
        },
    )

    assert set(script.scripts_with_entity(hass, "light.in_both")) == {
        "script.test1",
        "script.test2",
        "script.test3",
    }
    assert set(script.entities_in_script(hass, "script.test1")) == {
        "light.in_both",
        "light.in_first",
    }
    assert set(script.scripts_with_device(hass, device_in_both.id)) == {
        "script.test1",
        "script.test2",
    }
    assert set(script.devices_in_script(hass, "script.test2")) == {
        device_in_both.id,
        device_in_last.id,
    }
    assert set(script.scripts_with_area(hass, "area-in-both")) == {
        "script.test1",
        "script.test3",
    }
    assert set(script.areas_in_script(hass, "script.test3")) == {
        "area-in-both",
        "area-in-last",
    }
    assert set(script.scripts_with_floor(hass, "floor-in-both")) == {
        "script.test1",
        "script.test3",
    }
    assert set(script.floors_in_script(hass, "script.test3")) == {
        "floor-in-both",
        "floor-in-last",
    }
    assert set(script.scripts_with_label(hass, "label-in-both")) == {
        "script.test1",
        "script.test3",
    }
    assert set(script.labels_in_script(hass, "script.test3")) == {
        "label-in-both",
        "label-in-last",
    }
    assert script.blueprint_in_script(hass, "script.test3") is None


async def test_config_basic(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test passing info in config."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "alias": "Script Name",
                    "icon": "mdi:party",
                    "sequence": [],
                }
            }
        },
    )

    test_script = hass.states.get("script.test_script")
    assert test_script.name == "Script Name"
    assert test_script.attributes["icon"] == "mdi:party"

    entry = entity_registry.async_get("script.test_script")
    assert entry
    assert entry.unique_id == "test_script"


async def test_config_multiple_domains(hass: HomeAssistant) -> None:
    """Test splitting configuration over multiple domains."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "first_script": {
                    "alias": "Main domain",
                    "sequence": [],
                }
            },
            "script second": {
                "second_script": {
                    "alias": "Secondary domain",
                    "sequence": [],
                }
            },
        },
    )

    test_script = hass.states.get("script.first_script")
    assert test_script
    assert test_script.name == "Main domain"

    test_script = hass.states.get("script.second_script")
    assert test_script
    assert test_script.name == "Secondary domain"


async def test_logbook_humanify_script_started_event(hass: HomeAssistant) -> None:
    """Test humanifying script started event."""
    hass.config.components.add("recorder")
    await async_setup_component(hass, DOMAIN, {})
    await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event1, event2 = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_SCRIPT_STARTED,
                {ATTR_ENTITY_ID: "script.hello", ATTR_NAME: "Hello Script"},
            ),
            MockRow(
                EVENT_SCRIPT_STARTED,
                {ATTR_ENTITY_ID: "script.bye", ATTR_NAME: "Bye Script"},
            ),
        ],
    )

    assert event1["name"] == "Hello Script"
    assert event1["domain"] == "script"
    assert event1["message"] == "started"
    assert event1["entity_id"] == "script.hello"

    assert event2["name"] == "Bye Script"
    assert event2["domain"] == "script"
    assert event2["message"] == "started"
    assert event2["entity_id"] == "script.bye"


@pytest.mark.parametrize("concurrently", [False, True])
async def test_concurrent_script(hass: HomeAssistant, concurrently) -> None:
    """Test calling script concurrently or not."""
    if concurrently:
        call_script_2 = {
            "action": "script.turn_on",
            "data": {"entity_id": "script.script2"},
        }
    else:
        call_script_2 = {"action": "script.script2"}
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "script1": {
                    "mode": "parallel",
                    "sequence": [
                        call_script_2,
                        {
                            "wait_template": "{{ is_state('input_boolean.test1', 'on') }}"
                        },
                        {"action": "test.script", "data": {"value": "script1"}},
                    ],
                },
                "script2": {
                    "mode": "parallel",
                    "sequence": [
                        {"action": "test.script", "data": {"value": "script2a"}},
                        {
                            "wait_template": "{{ is_state('input_boolean.test2', 'on') }}"
                        },
                        {"action": "test.script", "data": {"value": "script2b"}},
                    ],
                },
            }
        },
    )

    service_called = asyncio.Event()
    service_values = []

    async def async_service_handler(service):
        nonlocal service_values
        service_values.append(service.data.get("value"))
        service_called.set()

    hass.services.async_register("test", "script", async_service_handler)
    hass.states.async_set("input_boolean.test1", "off")
    hass.states.async_set("input_boolean.test2", "off")

    await hass.services.async_call("script", "script1")
    await asyncio.wait_for(service_called.wait(), 1)
    service_called.clear()

    assert service_values[-1] == "script2a"
    assert script.is_on(hass, "script.script1")
    assert script.is_on(hass, "script.script2")

    if not concurrently:
        hass.states.async_set("input_boolean.test2", "on")
        await asyncio.wait_for(service_called.wait(), 1)
        service_called.clear()

        assert service_values[-1] == "script2b"

    hass.states.async_set("input_boolean.test1", "on")
    await asyncio.wait_for(service_called.wait(), 1)
    service_called.clear()

    assert service_values[-1] == "script1"
    assert concurrently == script.is_on(hass, "script.script2")

    if concurrently:
        hass.states.async_set("input_boolean.test2", "on")
        await asyncio.wait_for(service_called.wait(), 1)
        service_called.clear()

        assert service_values[-1] == "script2b"

    await hass.async_block_till_done()

    assert not script.is_on(hass, "script.script1")
    assert not script.is_on(hass, "script.script2")


async def test_script_variables(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test defining scripts."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "script1": {
                    "variables": {
                        "this_variable": "{{this.entity_id}}",
                        "test_var": "from_config",
                        "templated_config_var": "{{ var_from_service | default('config-default') }}",
                    },
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {
                                "value": "{{ test_var }}",
                                "templated_config_var": "{{ templated_config_var }}",
                                "this_template": "{{this.entity_id}}",
                                "this_variable": "{{this_variable}}",
                            },
                        },
                    ],
                },
                "script2": {
                    "variables": {
                        "test_var": "from_config",
                    },
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {
                                "value": "{{ test_var }}",
                            },
                        },
                    ],
                },
                "script3": {
                    "variables": {
                        "test_var": "{{ break + 1 }}",
                    },
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {
                                "value": "{{ test_var }}",
                            },
                        },
                    ],
                },
            }
        },
    )

    mock_calls = async_mock_service(hass, "test", "script")

    await hass.services.async_call(
        "script", "script1", {"var_from_service": "hello"}, blocking=True
    )

    assert len(mock_calls) == 1
    assert mock_calls[0].data["value"] == "from_config"
    assert mock_calls[0].data["templated_config_var"] == "hello"
    # Verify this available to all templates
    assert mock_calls[0].data.get("this_template") == "script.script1"
    # Verify this available during trigger variables rendering
    assert mock_calls[0].data.get("this_variable") == "script.script1"

    await hass.services.async_call(
        "script", "script1", {"test_var": "from_service"}, blocking=True
    )

    assert len(mock_calls) == 2
    assert mock_calls[1].data["value"] == "from_service"
    assert mock_calls[1].data["templated_config_var"] == "config-default"

    # Call script with vars but no templates in it
    await hass.services.async_call(
        "script", "script2", {"test_var": "from_service"}, blocking=True
    )

    assert len(mock_calls) == 3
    assert mock_calls[2].data["value"] == "from_service"

    assert "Error rendering variables" not in caplog.text
    with pytest.raises(TemplateError):
        await hass.services.async_call("script", "script3", blocking=True)
    assert "Error rendering variables" in caplog.text
    assert len(mock_calls) == 3

    await hass.services.async_call("script", "script3", {"break": 0}, blocking=True)

    assert len(mock_calls) == 4
    assert mock_calls[3].data["value"] == 1


async def test_script_this_var_always(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test script always has reference to this, even with no variables are configured."""

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "script1": {
                    "sequence": [
                        {
                            "action": "test.script",
                            "data": {
                                "this_template": "{{this.entity_id}}",
                            },
                        },
                    ],
                },
            },
        },
    )
    mock_calls = async_mock_service(hass, "test", "script")

    await hass.services.async_call("script", "script1", blocking=True)

    assert len(mock_calls) == 1
    # Verify this available to all templates
    assert mock_calls[0].data.get("this_template") == "script.script1"
    assert "Error rendering variables" not in caplog.text


async def test_script_restore_last_triggered(hass: HomeAssistant) -> None:
    """Test if last triggered is restored on start."""
    time = dt_util.utcnow()
    mock_restore_cache(
        hass,
        (
            State("script.no_last_triggered", STATE_OFF),
            State("script.last_triggered", STATE_OFF, {"last_triggered": time}),
        ),
    )
    hass.set_state(CoreState.starting)

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "no_last_triggered": {
                    "sequence": [{"delay": {"seconds": 5}}],
                },
                "last_triggered": {
                    "sequence": [{"delay": {"seconds": 5}}],
                },
            },
        },
    )

    state = hass.states.get("script.no_last_triggered")
    assert state
    assert state.attributes["last_triggered"] is None

    state = hass.states.get("script.last_triggered")
    assert state
    assert state.attributes["last_triggered"] == time


@pytest.mark.parametrize(
    ("script_mode", "warning_msg"),
    [
        (SCRIPT_MODE_PARALLEL, "Maximum number of runs exceeded"),
        (SCRIPT_MODE_QUEUED, "Disallowed recursion detected"),
        (SCRIPT_MODE_RESTART, "Disallowed recursion detected"),
        (SCRIPT_MODE_SINGLE, "Already running"),
    ],
)
async def test_recursive_script(
    hass: HomeAssistant, script_mode, warning_msg, caplog: pytest.LogCaptureFixture
) -> None:
    """Test recursive script calls does not deadlock."""
    # Make sure we cover all script modes
    assert [
        SCRIPT_MODE_PARALLEL,
        SCRIPT_MODE_QUEUED,
        SCRIPT_MODE_RESTART,
        SCRIPT_MODE_SINGLE,
    ] == SCRIPT_MODE_CHOICES

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "script1": {
                    "mode": script_mode,
                    "sequence": [
                        {"action": "script.script1"},
                        {"action": "test.script"},
                    ],
                },
            }
        },
    )

    service_called = asyncio.Event()

    async def async_service_handler(service):
        service_called.set()

    hass.services.async_register("test", "script", async_service_handler)

    await hass.services.async_call("script", "script1")
    await asyncio.wait_for(service_called.wait(), 1)

    assert warning_msg in caplog.text


@pytest.mark.parametrize(
    ("script_mode", "warning_msg"),
    [
        (SCRIPT_MODE_PARALLEL, "Maximum number of runs exceeded"),
        (SCRIPT_MODE_QUEUED, "Disallowed recursion detected"),
        (SCRIPT_MODE_RESTART, "Disallowed recursion detected"),
        (SCRIPT_MODE_SINGLE, "Already running"),
    ],
)
async def test_recursive_script_indirect(
    hass: HomeAssistant, script_mode, warning_msg, caplog: pytest.LogCaptureFixture
) -> None:
    """Test recursive script calls does not deadlock."""
    # Make sure we cover all script modes
    assert [
        SCRIPT_MODE_PARALLEL,
        SCRIPT_MODE_QUEUED,
        SCRIPT_MODE_RESTART,
        SCRIPT_MODE_SINGLE,
    ] == SCRIPT_MODE_CHOICES

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "script1": {
                    "mode": script_mode,
                    "sequence": [
                        {"action": "script.script2"},
                    ],
                },
                "script2": {
                    "mode": script_mode,
                    "sequence": [
                        {"action": "script.script3"},
                    ],
                },
                "script3": {
                    "mode": script_mode,
                    "sequence": [
                        {"action": "script.script4"},
                    ],
                },
                "script4": {
                    "mode": script_mode,
                    "sequence": [
                        {"action": "script.script1"},
                        {"action": "test.script"},
                    ],
                },
            }
        },
    )

    service_called = asyncio.Event()

    async def async_service_handler(service):
        service_called.set()

    hass.services.async_register("test", "script", async_service_handler)

    await hass.services.async_call("script", "script1")
    await asyncio.wait_for(service_called.wait(), 1)

    assert warning_msg in caplog.text


@pytest.mark.parametrize(
    "script_mode", [SCRIPT_MODE_PARALLEL, SCRIPT_MODE_QUEUED, SCRIPT_MODE_RESTART]
)
@pytest.mark.parametrize("wait_for_stop_scripts_after_shutdown", [True])
async def test_recursive_script_turn_on(
    hass: HomeAssistant, script_mode, caplog: pytest.LogCaptureFixture
) -> None:
    """Test script turning itself on.

    - Illegal recursion detection should not be triggered
    - Home Assistant should not hang on shut down
    - SCRIPT_MODE_SINGLE is not relevant because suca script can't turn itself on
    """
    # Make sure we cover all script modes
    assert [
        SCRIPT_MODE_PARALLEL,
        SCRIPT_MODE_QUEUED,
        SCRIPT_MODE_RESTART,
        SCRIPT_MODE_SINGLE,
    ] == SCRIPT_MODE_CHOICES
    stop_scripts_at_shutdown_called = asyncio.Event()
    real_stop_scripts_at_shutdown = _async_stop_scripts_at_shutdown

    async def stop_scripts_at_shutdown(*args):
        await real_stop_scripts_at_shutdown(*args)
        stop_scripts_at_shutdown_called.set()

    with patch(
        "homeassistant.helpers.script._async_stop_scripts_at_shutdown",
        wraps=stop_scripts_at_shutdown,
    ):
        assert await async_setup_component(
            hass,
            script.DOMAIN,
            {
                script.DOMAIN: {
                    "script1": {
                        "mode": script_mode,
                        "sequence": [
                            {
                                "choose": {
                                    "conditions": {
                                        "condition": "template",
                                        "value_template": "{{ request == 'step_2' }}",
                                    },
                                    "sequence": {"action": "test.script_done"},
                                },
                                "default": {
                                    "action": "script.turn_on",
                                    "data": {
                                        "entity_id": "script.script1",
                                        "variables": {"request": "step_2"},
                                    },
                                },
                            },
                            {
                                "action": "script.turn_on",
                                "data": {"entity_id": "script.script1"},
                            },
                        ],
                    }
                }
            },
        )

        service_called = asyncio.Event()

        async def async_service_handler(service):
            if service.service == "script_done":
                service_called.set()

        hass.services.async_register("test", "script_done", async_service_handler)

        await hass.services.async_call("script", "script1")
        await asyncio.wait_for(service_called.wait(), 1)

        # Trigger 1st stage script shutdown
        hass.set_state(CoreState.stopping)
        hass.bus.async_fire("homeassistant_stop")
        await asyncio.wait_for(stop_scripts_at_shutdown_called.wait(), 1)

        # Trigger 2nd stage script shutdown
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()

        assert "Disallowed recursion detected" not in caplog.text


async def test_setup_with_duplicate_scripts(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with duplicate configs."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script one": {
                "duplicate": {
                    "sequence": [],
                },
            },
            "script two": {
                "duplicate": {
                    "sequence": [],
                },
            },
        },
    )
    assert "Duplicate script detected with name: 'duplicate'" in caplog.text
    assert len(hass.states.async_entity_ids("script")) == 1


async def test_websocket_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test config command."""
    config = {
        "alias": "hello",
        "sequence": [{"action": "light.turn_on"}],
    }
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "hello": config,
            },
        },
    )
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "script/config",
            "entity_id": "script.hello",
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"config": config}

    await client.send_json(
        {
            "id": 6,
            "type": "script/config",
            "entity_id": "script.not_exist",
        }
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_script_service_changed_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the script service works for scripts with overridden entity_id."""
    entry = entity_registry.async_get_or_create("script", "script", "test")
    entry = entity_registry.async_update_entity(
        entry.entity_id, new_entity_id="script.custom_entity_id"
    )
    assert entry.entity_id == "script.custom_entity_id"

    calls = []

    @callback
    def record_call(service):
        """Add recorded event to set."""
        calls.append(service)

    hass.services.async_register("test", "script", record_call)

    # Make sure the service of a script with overridden entity_id works
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": {
                        "action": "test.script",
                        "data_template": {"entity_id": "{{ this.entity_id }}"},
                    }
                }
            }
        },
    )

    await hass.services.async_call(DOMAIN, "test", {"greeting": "world"})

    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["entity_id"] == "script.custom_entity_id"

    # Change entity while the script entity is loaded, and make sure the service still works
    entry = entity_registry.async_update_entity(
        entry.entity_id, new_entity_id="script.custom_entity_id_2"
    )
    assert entry.entity_id == "script.custom_entity_id_2"
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "test", {"greeting": "world"})
    await hass.async_block_till_done()

    assert len(calls) == 2
    assert calls[1].data["entity_id"] == "script.custom_entity_id_2"


async def test_blueprint_script(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test blueprint script."""
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test_script": {
                    "use_blueprint": {
                        "path": "test_service.yaml",
                        "input": {
                            "service_to_call": "test.script",
                        },
                    }
                }
            }
        },
    )
    await hass.services.async_call(
        "script", "test_script", {"var_from_service": "hello"}, blocking=True
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert script.blueprint_in_script(hass, "script.test_script") == "test_service.yaml"
    assert script.scripts_with_blueprint(hass, "test_service.yaml") == [
        "script.test_script"
    ]


@pytest.mark.parametrize(
    ("blueprint_inputs", "problem", "details"),
    [
        (
            # No input
            {},
            "Failed to generate script from blueprint",
            "Missing input service_to_call",
        ),
        (
            # Missing input
            {"a_number": 5},
            "Failed to generate script from blueprint",
            "Missing input service_to_call",
        ),
        (
            # Wrong input
            {
                "trigger_event": "blueprint_event",
                "service_to_call": {"dict": "not allowed"},
                "a_number": 5,
            },
            "Blueprint 'Call service' generated invalid script",
            "value should be a string for dictionary value @ data['sequence'][0]['action']",
        ),
    ],
)
async def test_blueprint_script_bad_config(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    blueprint_inputs,
    problem,
    details,
) -> None:
    """Test blueprint script with bad inputs."""
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test_script": {
                    "use_blueprint": {
                        "path": "test_service.yaml",
                        "input": blueprint_inputs,
                    }
                }
            }
        },
    )
    assert problem in caplog.text
    assert details in caplog.text

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    issue = "validation_failed_blueprint"
    assert issues[0]["issue_id"] == f"script.test_script_{issue}"
    assert issues[0]["translation_key"] == issue
    assert issues[0]["translation_placeholders"] == {
        "edit": "/config/script/edit/test_script",
        "entity_id": "script.test_script",
        "error": ANY,
        "name": "test_script",
    }
    assert issues[0]["translation_placeholders"]["error"].startswith(details)


async def test_blueprint_script_fails_substitution(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blueprint script with bad inputs."""
    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml.UndefinedSubstitution("blah"),
    ):
        assert await async_setup_component(
            hass,
            script.DOMAIN,
            {
                script.DOMAIN: {
                    "test_script": {
                        "use_blueprint": {
                            "path": "test_service.yaml",
                            "input": {
                                "service_to_call": "test.automation",
                            },
                        }
                    }
                }
            },
        )
    assert (
        "Blueprint 'Call service' failed to generate script with inputs "
        "{'service_to_call': 'test.automation'}: No substitution found for input blah"
        in caplog.text
    )

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    issue = "validation_failed_blueprint"
    assert issues[0]["issue_id"] == f"script.test_script_{issue}"
    assert issues[0]["translation_key"] == issue
    assert issues[0]["translation_placeholders"] == {
        "edit": "/config/script/edit/test_script",
        "entity_id": "script.test_script",
        "error": "No substitution found for input blah",
        "name": "test_script",
    }


@pytest.mark.parametrize("response", [{"value": 5}, '{"value": 5}'])
async def test_responses(hass: HomeAssistant, response: Any) -> None:
    """Test we can get responses."""
    mock_restore_cache(hass, ())
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": [
                        {
                            "variables": {"test_var": {"response": response}},
                        },
                        {
                            "stop": "done",
                            "response_variable": "test_var",
                        },
                    ]
                }
            }
        },
    )

    assert await hass.services.async_call(
        DOMAIN, "test", {"greeting": "world"}, blocking=True, return_response=True
    ) == {"response": response}
    # Validate we can also call it without return_response
    assert (
        await hass.services.async_call(
            DOMAIN, "test", {"greeting": "world"}, blocking=True, return_response=False
        )
        is None
    )


async def test_responses_no_response(hass: HomeAssistant) -> None:
    """Test response variable not set."""
    mock_restore_cache(hass, ())
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test": {
                    "sequence": [
                        {
                            "stop": "done",
                            "response_variable": "test_var",
                        },
                    ]
                }
            }
        },
    )

    # Validate we can call it with return_response
    assert (
        await hass.services.async_call(
            DOMAIN, "test", {"greeting": "world"}, blocking=True, return_response=True
        )
        == {}
    )
    # Validate we can also call it without return_response
    assert (
        await hass.services.async_call(
            DOMAIN, "test", {"greeting": "world"}, blocking=True, return_response=False
        )
        is None
    )


async def test_script_queued_mode(hass: HomeAssistant) -> None:
    """Test calling a queued mode script called in parallel."""
    calls = 0

    async def async_service_handler(*args, **kwargs) -> None:
        """Service that simulates doing background I/O."""
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)

    hass.services.async_register("test", "simulated_remote", async_service_handler)
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test_main": {
                    "sequence": [
                        {
                            "parallel": [
                                {"action": "script.test_sub"},
                                {"action": "script.test_sub"},
                                {"action": "script.test_sub"},
                                {"action": "script.test_sub"},
                            ]
                        }
                    ]
                },
                "test_sub": {
                    "mode": "queued",
                    "sequence": [
                        {"action": "test.simulated_remote"},
                    ],
                },
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call("script", "test_main", blocking=True)
    assert calls == 4
