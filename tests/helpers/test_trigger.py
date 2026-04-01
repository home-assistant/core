"""The tests for the trigger helper."""

from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext as does_not_raise
import io
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch

import pytest
from pytest_unordered import unordered
import voluptuous as vol

from homeassistant.components import automation
from homeassistant.components.sun import DOMAIN as SUN_DOMAIN
from homeassistant.components.system_health import DOMAIN as SYSTEM_HEALTH_DOMAIN
from homeassistant.components.tag import DOMAIN as TAG_DOMAIN
from homeassistant.components.text import DOMAIN as TEXT_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, trigger
from homeassistant.helpers.automation import (
    DomainSpec,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.trigger import (
    DATA_PLUGGABLE_ACTIONS,
    TRIGGERS,
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityTriggerBase,
    PluggableAction,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    _async_get_trigger_platform,
    async_initialize_triggers,
    async_validate_trigger_config,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration, async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import MockModule, MockPlatform, mock_integration, mock_platform
from tests.typing import WebSocketGenerator


async def test_bad_trigger_platform(hass: HomeAssistant) -> None:
    """Test bad trigger platform."""
    with pytest.raises(vol.Invalid) as ex:
        await async_validate_trigger_config(hass, [{"platform": "not_a_platform"}])
    assert "Invalid trigger 'not_a_platform' specified" in str(ex)


async def test_trigger_subtype(hass: HomeAssistant) -> None:
    """Test trigger subtypes."""
    with patch(
        "homeassistant.helpers.trigger.async_get_integration",
        return_value=MagicMock(async_get_platform=AsyncMock()),
    ) as integration_mock:
        await _async_get_trigger_platform(hass, "test.subtype")
        assert integration_mock.call_args == call(hass, "test")


async def test_trigger_variables(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test trigger variables."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "event",
                    "event_type": "test_event",
                    "variables": {
                        "name": "Paulus",
                        "via_event": "{{ trigger.event.event_type }}",
                    },
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"hello": "{{ name }} + {{ via_event }}"},
                },
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["hello"] == "Paulus + test_event"


async def test_if_disabled_trigger_not_firing(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test disabled triggers don't fire."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "platform": "event",
                        "event_type": "enabled_trigger_event",
                    },
                    {
                        "enabled": False,
                        "platform": "event",
                        "event_type": "disabled_trigger_event",
                    },
                ],
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    hass.bus.async_fire("disabled_trigger_event")
    await hass.async_block_till_done()
    assert not service_calls

    hass.bus.async_fire("enabled_trigger_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_trigger_enabled_templates(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test triggers enabled by template."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "enabled": "{{ 'some text' }}",
                        "platform": "event",
                        "event_type": "truthy_template_trigger_event",
                    },
                    {
                        "enabled": "{{ 3 == 4 }}",
                        "platform": "event",
                        "event_type": "falsy_template_trigger_event",
                    },
                    {
                        "enabled": False,  # eg. from a blueprints input defaulting to `false`
                        "platform": "event",
                        "event_type": "falsy_trigger_event",
                    },
                    {
                        "enabled": "some text",  # eg. from a blueprints input value
                        "platform": "event",
                        "event_type": "truthy_trigger_event",
                    },
                ],
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    hass.bus.async_fire("falsy_template_trigger_event")
    await hass.async_block_till_done()
    assert not service_calls

    hass.bus.async_fire("falsy_trigger_event")
    await hass.async_block_till_done()
    assert not service_calls

    hass.bus.async_fire("truthy_template_trigger_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.bus.async_fire("truthy_trigger_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 2


async def test_nested_trigger_list(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test triggers within nested list."""

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "triggers": {
                            "platform": "event",
                            "event_type": "trigger_1",
                        },
                    },
                    {
                        "platform": "event",
                        "event_type": "trigger_2",
                    },
                    {"triggers": []},
                    {"triggers": None},
                    {
                        "triggers": [
                            {
                                "platform": "event",
                                "event_type": "trigger_3",
                            },
                            {
                                "platform": "event",
                                "event_type": "trigger_4",
                            },
                        ],
                    },
                ],
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    hass.bus.async_fire("trigger_1")
    await hass.async_block_till_done()
    assert len(service_calls) == 1

    hass.bus.async_fire("trigger_2")
    await hass.async_block_till_done()
    assert len(service_calls) == 2

    hass.bus.async_fire("trigger_none")
    await hass.async_block_till_done()
    assert len(service_calls) == 2

    hass.bus.async_fire("trigger_3")
    await hass.async_block_till_done()
    assert len(service_calls) == 3

    hass.bus.async_fire("trigger_4")
    await hass.async_block_till_done()
    assert len(service_calls) == 4


async def test_trigger_enabled_template_limited(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test triggers enabled invalid template."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "enabled": "{{ states('sensor.limited') }}",  # only limited template supported
                        "platform": "event",
                        "event_type": "test_event",
                    },
                ],
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert not service_calls
    assert "Error rendering enabled template" in caplog.text


async def test_trigger_alias(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test triggers support aliases."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": [
                    {
                        "alias": "My event",
                        "platform": "event",
                        "event_type": "trigger_event",
                    }
                ],
                "action": {
                    "service": "test.automation",
                    "data_template": {"alias": "{{ trigger.alias }}"},
                },
            }
        },
    )

    hass.bus.async_fire("trigger_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["alias"] == "My event"
    assert (
        "Automation trigger 'My event' triggered by event 'trigger_event'"
        in caplog.text
    )


async def test_async_initialize_triggers(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_initialize_triggers with different action types."""

    log_cb = MagicMock()

    action_calls = []

    trigger_config = await async_validate_trigger_config(
        hass,
        [
            {
                "platform": "event",
                "event_type": ["trigger_event"],
                "variables": {
                    "name": "Paulus",
                    "via_event": "{{ trigger.event.event_type }}",
                },
            }
        ],
    )

    async def async_action(*args):
        action_calls.append([*args])

    @callback
    def cb_action(*args):
        action_calls.append([*args])

    def non_cb_action(*args):
        action_calls.append([*args])

    for action in (async_action, cb_action, non_cb_action):
        action_calls = []

        unsub = await async_initialize_triggers(
            hass,
            trigger_config,
            action,
            "test",
            "",
            log_cb,
        )
        await hass.async_block_till_done()

        hass.bus.async_fire("trigger_event")
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert len(action_calls) == 1
        assert action_calls[0][0]["name"] == "Paulus"
        assert action_calls[0][0]["via_event"] == "trigger_event"
        log_cb.assert_called_once_with(ANY, "Initialized trigger")

        log_cb.reset_mock()
        unsub()


async def test_pluggable_action(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test normal behavior of pluggable actions."""
    update_1 = MagicMock()
    update_2 = MagicMock()
    action_1 = AsyncMock()
    action_2 = AsyncMock()
    trigger_1 = {"domain": "test", "device": "1"}
    trigger_2 = {"domain": "test", "device": "2"}
    variables_1 = {"source": "test 1"}
    variables_2 = {"source": "test 2"}
    context_1 = Context()
    context_2 = Context()

    plug_1 = PluggableAction(update_1)
    plug_2 = PluggableAction(update_2)

    # Verify plug is inactive without triggers
    remove_plug_1 = plug_1.async_register(hass, trigger_1)
    assert not plug_1
    assert not plug_2

    # Verify plug remain inactive with non matching trigger
    remove_attach_2 = PluggableAction.async_attach_trigger(
        hass, trigger_2, action_2, variables_2
    )
    assert not plug_1
    assert not plug_2
    update_1.assert_not_called()
    update_2.assert_not_called()

    # Verify plug is active, and update when matching trigger attaches
    remove_attach_1 = PluggableAction.async_attach_trigger(
        hass, trigger_1, action_1, variables_1
    )
    assert plug_1
    assert not plug_2
    update_1.assert_called()
    update_1.reset_mock()
    update_2.assert_not_called()

    # Verify a non registered plug is inactive
    remove_plug_1()
    assert not plug_1
    assert not plug_2

    # Verify a plug registered to existing trigger is true
    remove_plug_1 = plug_1.async_register(hass, trigger_1)
    assert plug_1
    assert not plug_2

    remove_plug_2 = plug_2.async_register(hass, trigger_2)
    assert plug_1
    assert plug_2

    # Verify no actions should have been triggered so far
    action_1.assert_not_called()
    action_2.assert_not_called()

    # Verify action is triggered with correct data
    await plug_1.async_run(hass, context_1)
    await plug_2.async_run(hass, context_2)
    action_1.assert_called_with(variables_1, context_1)
    action_2.assert_called_with(variables_2, context_2)

    # Verify plug goes inactive if trigger is removed
    remove_attach_1()
    assert not plug_1

    # Verify registry is cleaned when no plugs nor triggers are attached
    assert hass.data[DATA_PLUGGABLE_ACTIONS]
    remove_plug_1()
    remove_plug_2()
    remove_attach_2()
    assert not hass.data[DATA_PLUGGABLE_ACTIONS]
    assert not plug_2


class TriggerActionFunctionTypeHelper:
    """Helper for testing different trigger action function types."""

    def __init__(self) -> None:
        """Init helper."""
        self.action_calls = []

    @callback
    def cb_action(self, *args):
        """Callback action."""
        self.action_calls.append([*args])

    def sync_action(self, *args):
        """Sync action."""
        self.action_calls.append([*args])

    async def async_action(self, *args):
        """Async action."""
        self.action_calls.append([*args])


@pytest.mark.parametrize("action_method", ["cb_action", "sync_action", "async_action"])
async def test_platform_multiple_triggers(
    hass: HomeAssistant, action_method: str
) -> None:
    """Test a trigger platform with multiple trigger."""

    class MockTrigger(Trigger):
        """Mock trigger."""

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    class MockTrigger1(MockTrigger):
        """Mock trigger 1."""

        async def async_attach_runner(
            self, run_action: TriggerActionRunner
        ) -> CALLBACK_TYPE:
            """Attach a trigger."""
            run_action({"extra": "test_trigger_1"}, "trigger 1 desc")

    class MockTrigger2(MockTrigger):
        """Mock trigger 2."""

        async def async_attach_runner(
            self, run_action: TriggerActionRunner
        ) -> CALLBACK_TYPE:
            """Attach a trigger."""
            run_action({"extra": "test_trigger_2"}, "trigger 2 desc")

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "_": MockTrigger1,
            "trig_2": MockTrigger2,
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    config_1 = [{"platform": "test"}]
    config_2 = [{"platform": "test.trig_2", "options": {"x": 1}}]
    config_3 = [{"platform": "test.unknown_trig"}]
    assert await async_validate_trigger_config(hass, config_1) == config_1
    assert await async_validate_trigger_config(hass, config_2) == config_2
    with pytest.raises(
        vol.Invalid, match="Invalid trigger 'test.unknown_trig' specified"
    ):
        await async_validate_trigger_config(hass, config_3)

    log_cb = MagicMock()

    action_helper = TriggerActionFunctionTypeHelper()
    action_method = getattr(action_helper, action_method)

    await async_initialize_triggers(hass, config_1, action_method, "test", "", log_cb)
    await hass.async_block_till_done()
    assert len(action_helper.action_calls) == 1
    assert action_helper.action_calls[0][0] == {
        "trigger": {
            "alias": None,
            "description": "trigger 1 desc",
            "extra": "test_trigger_1",
            "id": "0",
            "idx": "0",
            "platform": "test",
        }
    }
    action_helper.action_calls.clear()

    await async_initialize_triggers(hass, config_2, action_method, "test", "", log_cb)
    await hass.async_block_till_done()
    assert len(action_helper.action_calls) == 1
    assert action_helper.action_calls[0][0] == {
        "trigger": {
            "alias": None,
            "description": "trigger 2 desc",
            "extra": "test_trigger_2",
            "id": "0",
            "idx": "0",
            "platform": "test.trig_2",
        }
    }
    action_helper.action_calls.clear()

    with pytest.raises(KeyError):
        await async_initialize_triggers(
            hass, config_3, action_method, "test", "", log_cb
        )


async def test_platform_migrate_trigger(hass: HomeAssistant) -> None:
    """Test a trigger platform with a migration."""

    OPTIONS_SCHEMA_DICT = {
        vol.Required("option_1"): str,
        vol.Optional("option_2"): int,
    }

    class MockTrigger(Trigger):
        """Mock trigger."""

        @classmethod
        async def async_validate_complete_config(
            cls, hass: HomeAssistant, complete_config: ConfigType
        ) -> ConfigType:
            """Validate complete config."""
            complete_config = move_top_level_schema_fields_to_options(
                complete_config, OPTIONS_SCHEMA_DICT
            )
            return await super().async_validate_complete_config(hass, complete_config)

        @classmethod
        async def async_validate_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "_": MockTrigger,
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    config_1 = [{"platform": "test", "option_1": "value_1", "option_2": 2}]
    config_2 = [{"platform": "test", "option_1": "value_1"}]
    config_3 = [{"platform": "test", "options": {"option_1": "value_1", "option_2": 2}}]
    config_4 = [{"platform": "test", "options": {"option_1": "value_1"}}]

    assert await async_validate_trigger_config(hass, config_1) == config_3
    assert await async_validate_trigger_config(hass, config_2) == config_4
    assert await async_validate_trigger_config(hass, config_3) == config_3
    assert await async_validate_trigger_config(hass, config_4) == config_4


async def test_platform_backwards_compatibility_for_new_style_configs(
    hass: HomeAssistant,
) -> None:
    """Test backwards compatibility for old-style triggers with new-style configs."""

    class MockTriggerPlatform:
        """Mock trigger platform."""

        TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
            {
                vol.Required("option_1"): str,
                vol.Optional("option_2"): int,
            }
        )

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", MockTriggerPlatform())

    config_old_style = [{"platform": "test", "option_1": "value_1", "option_2": 2}]
    result = await async_validate_trigger_config(hass, config_old_style)
    assert result == config_old_style

    config_new_style = [
        {"platform": "test", "options": {"option_1": "value_1", "option_2": 2}}
    ]
    result = await async_validate_trigger_config(hass, config_new_style)
    assert result == config_old_style


async def test_get_trigger_platform_registers_triggers(
    hass: HomeAssistant,
) -> None:
    """Test _async_get_trigger_platform registers triggers and notifies subscribers."""

    class MockTrigger(Trigger):
        """Mock trigger."""

        async def async_attach_runner(
            self, run_action: TriggerActionRunner
        ) -> CALLBACK_TYPE:
            return lambda: None

    async def async_get_triggers(
        hass: HomeAssistant,
    ) -> dict[str, type[Trigger]]:
        return {"trig_a": MockTrigger, "trig_b": MockTrigger}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    subscriber_events: list[set[str]] = []

    async def subscriber(new_triggers: set[str]) -> None:
        subscriber_events.append(new_triggers)

    trigger.async_subscribe_platform_events(hass, subscriber)

    assert "test.trig_a" not in hass.data[TRIGGERS]
    assert "test.trig_b" not in hass.data[TRIGGERS]

    # First call registers all triggers from the platform and notifies subscribers
    await _async_get_trigger_platform(hass, "test.trig_a")

    assert hass.data[TRIGGERS]["test.trig_a"] == "test"
    assert hass.data[TRIGGERS]["test.trig_b"] == "test"
    assert len(subscriber_events) == 1
    assert subscriber_events[0] == {"test.trig_a", "test.trig_b"}

    # Subsequent calls are idempotent — no re-registration or re-notification
    await _async_get_trigger_platform(hass, "test.trig_a")
    await _async_get_trigger_platform(hass, "test.trig_b")
    assert len(subscriber_events) == 1


@pytest.mark.parametrize(
    "sun_trigger_descriptions",
    [
        """
        _:
          fields:
            event:
              example: sunrise
              selector:
                select:
                  options:
                    - sunrise
                    - sunset
            offset:
              selector:
                time: null
        """,
        """
        .anchor: &anchor
          - sunrise
          - sunset
        _:
          fields:
            event:
              example: sunrise
              selector:
                select:
                  options: *anchor
            offset:
              selector:
                time: null
        """,
    ],
)
async def test_async_get_all_descriptions(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    sun_trigger_descriptions: str,
) -> None:
    """Test async_get_all_descriptions."""
    tag_trigger_descriptions = """
        _:
          target:
            entity:
              domain: alarm_control_panel
        """
    text_trigger_descriptions = """
        changed:
          target:
            entity:
              domain: text
        """

    ws_client = await hass_ws_client(hass)

    assert await async_setup_component(hass, SUN_DOMAIN, {})
    assert await async_setup_component(hass, SYSTEM_HEALTH_DOMAIN, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        if fname.endswith("sun/triggers.yaml"):
            trigger_descriptions = sun_trigger_descriptions
        elif fname.endswith("tag/triggers.yaml"):
            trigger_descriptions = tag_trigger_descriptions
        elif fname.endswith("text/triggers.yaml"):
            trigger_descriptions = text_trigger_descriptions
        with io.StringIO(trigger_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "homeassistant.helpers.trigger._load_triggers_files",
            side_effect=trigger._load_triggers_files,
        ) as proxy_load_triggers_files,
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        descriptions = await trigger.async_get_all_descriptions(hass)

    # Test we only load triggers.yaml for integrations with triggers,
    # system_health has no triggers
    assert proxy_load_triggers_files.mock_calls[0][1][0] == unordered(
        [
            await async_get_integration(hass, SUN_DOMAIN),
        ]
    )

    # system_health does not have triggers and should not be in descriptions
    expected_descriptions = {
        "sun": {
            "fields": {
                "event": {
                    "example": "sunrise",
                    "selector": {
                        "select": {
                            "custom_value": False,
                            "multiple": False,
                            "options": ["sunrise", "sunset"],
                            "sort": False,
                        }
                    },
                },
                "offset": {"selector": {"time": {}}},
            }
        }
    }

    assert descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is descriptions

    # Load the tag integration and check a new cache object is created
    assert await async_setup_component(hass, TAG_DOMAIN, {})
    await hass.async_block_till_done()

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        new_descriptions = await trigger.async_get_all_descriptions(hass)
    assert new_descriptions is not descriptions
    # The tag trigger should now be present
    expected_descriptions |= {
        "tag": {
            "target": {
                "entity": [
                    {
                        "domain": ["alarm_control_panel"],
                    }
                ],
            },
            "fields": {},
        },
    }
    assert new_descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is new_descriptions

    # Load the text integration and check a new cache object is created
    assert await async_setup_component(hass, TEXT_DOMAIN, {})
    await hass.async_block_till_done()

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        new_descriptions = await trigger.async_get_all_descriptions(hass)
    assert new_descriptions is not descriptions
    # No text triggers added, they are gated by the automation.new_triggers_conditions
    # labs flag
    assert new_descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is new_descriptions

    # Enable the new_triggers_conditions flag and verify text triggers are loaded
    assert await async_setup_component(hass, "labs", {})

    await ws_client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "automation",
            "preview_feature": "new_triggers_conditions",
            "enabled": True,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        new_descriptions = await trigger.async_get_all_descriptions(hass)
    assert new_descriptions is not descriptions
    # The text triggers should now be present
    assert new_descriptions == expected_descriptions | {
        "text.changed": {
            "fields": {},
            "target": {
                "entity": [
                    {
                        "domain": [
                            "text",
                        ],
                    },
                ],
            },
        },
    }

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is new_descriptions

    # Disable the new_triggers_conditions flag and verify text triggers are removed
    assert await async_setup_component(hass, "labs", {})

    await ws_client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "automation",
            "preview_feature": "new_triggers_conditions",
            "enabled": False,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        new_descriptions = await trigger.async_get_all_descriptions(hass)
    assert new_descriptions is not descriptions
    # The text triggers should no longer be present
    assert new_descriptions == expected_descriptions

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is new_descriptions


@pytest.mark.parametrize(
    ("yaml_error", "expected_message"),
    [
        (
            FileNotFoundError("Blah"),
            "Unable to find triggers.yaml for the sun integration",
        ),
        (
            HomeAssistantError("Test error"),
            "Unable to parse triggers.yaml for the sun integration: Test error",
        ),
    ],
)
async def test_async_get_all_descriptions_with_yaml_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    yaml_error: Exception,
    expected_message: str,
) -> None:
    """Test async_get_all_descriptions."""
    assert await async_setup_component(hass, SUN_DOMAIN, {})
    await hass.async_block_till_done()

    def _load_yaml_dict(fname, secrets=None):
        raise yaml_error

    with (
        patch(
            "homeassistant.helpers.trigger.load_yaml_dict",
            side_effect=_load_yaml_dict,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        descriptions = await trigger.async_get_all_descriptions(hass)

    assert descriptions == {SUN_DOMAIN: None}

    assert expected_message in caplog.text


async def test_async_get_all_descriptions_with_bad_description(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_get_all_descriptions."""
    sun_service_descriptions = """
        _:
          fields: not_a_dict
    """

    assert await async_setup_component(hass, SUN_DOMAIN, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        with io.StringIO(sun_service_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "annotatedyaml.loader.load_yaml",
            side_effect=_load_yaml,
        ),
        patch.object(Integration, "has_triggers", return_value=True),
    ):
        descriptions = await trigger.async_get_all_descriptions(hass)

    assert descriptions == {SUN_DOMAIN: None}

    assert (
        "Unable to parse triggers.yaml for the sun integration: "
        "expected a dictionary for dictionary value @ data['_']['fields']"
    ) in caplog.text


async def test_invalid_trigger_platform(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid trigger platform."""
    mock_integration(hass, MockModule("test", async_setup=AsyncMock(return_value=True)))
    mock_platform(hass, "test.trigger", MockPlatform())

    await async_setup_component(hass, "test", {})

    assert "Integration test does not provide trigger support, skipping" in caplog.text


@patch("annotatedyaml.loader.load_yaml")
@patch.object(Integration, "has_triggers", return_value=True)
async def test_subscribe_triggers(
    mock_has_triggers: Mock,
    mock_load_yaml: Mock,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger.async_subscribe_platform_events."""
    sun_trigger_descriptions = """
        _: {}
        """

    def _load_yaml(fname, secrets=None):
        if fname.endswith("sun/triggers.yaml"):
            trigger_descriptions = sun_trigger_descriptions
        else:
            raise FileNotFoundError
        with io.StringIO(trigger_descriptions) as file:
            return parse_yaml(file)

    mock_load_yaml.side_effect = _load_yaml

    async def broken_subscriber(_):
        """Simulate a broken subscriber."""
        raise Exception("Boom!")  # noqa: TRY002

    trigger_events = []

    async def good_subscriber(new_triggers: set[str]):
        """Simulate a working subscriber."""
        trigger_events.append(new_triggers)

    trigger.async_subscribe_platform_events(hass, broken_subscriber)
    trigger.async_subscribe_platform_events(hass, good_subscriber)

    assert await async_setup_component(hass, "sun", {})
    assert trigger_events == [{"sun"}]
    assert "Error while notifying trigger platform listener" in caplog.text


@patch("annotatedyaml.loader.load_yaml")
@patch.object(Integration, "has_triggers", return_value=True)
@pytest.mark.parametrize(
    ("new_triggers_conditions_enabled", "expected_events"),
    [
        (
            True,
            [
                {
                    "light.brightness_changed",
                    "light.brightness_crossed_threshold",
                    "light.turned_off",
                    "light.turned_on",
                }
            ],
        ),
        (False, []),
    ],
)
async def test_subscribe_triggers_experimental_triggers(
    mock_has_triggers: Mock,
    mock_load_yaml: Mock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    new_triggers_conditions_enabled: bool,
    expected_events: list[set[str]],
) -> None:
    """Test trigger.async_subscribe_platform_events doesn't send events for disabled triggers."""
    # Return empty triggers.yaml for light integration, the actual trigger descriptions
    # are irrelevant for this test
    light_trigger_descriptions = ""

    def _load_yaml(fname, secrets=None):
        if fname.endswith("light/triggers.yaml"):
            trigger_descriptions = light_trigger_descriptions
        else:
            raise FileNotFoundError
        with io.StringIO(trigger_descriptions) as file:
            return parse_yaml(file)

    mock_load_yaml.side_effect = _load_yaml

    trigger_events = []

    async def good_subscriber(new_triggers: set[str]):
        """Simulate a working subscriber."""
        trigger_events.append(new_triggers)

    ws_client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "labs", {})
    await ws_client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "automation",
            "preview_feature": "new_triggers_conditions",
            "enabled": new_triggers_conditions_enabled,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    trigger.async_subscribe_platform_events(hass, good_subscriber)

    assert await async_setup_component(hass, "light", {})
    await hass.async_block_till_done()
    assert trigger_events == expected_events


@patch("annotatedyaml.loader.load_yaml")
@patch.object(Integration, "has_triggers", return_value=True)
@patch(
    "homeassistant.components.light.trigger.async_get_triggers",
    new=AsyncMock(return_value={}),
)
async def test_subscribe_triggers_no_triggers(
    mock_has_triggers: Mock,
    mock_load_yaml: Mock,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger.async_subscribe_platform_events doesn't send events for platforms without triggers."""
    # Return empty triggers.yaml for light integration, the actual trigger descriptions
    # are irrelevant for this test
    light_trigger_descriptions = ""

    def _load_yaml(fname, secrets=None):
        if fname.endswith("light/triggers.yaml"):
            trigger_descriptions = light_trigger_descriptions
        else:
            raise FileNotFoundError
        with io.StringIO(trigger_descriptions) as file:
            return parse_yaml(file)

    mock_load_yaml.side_effect = _load_yaml

    trigger_events = []

    async def good_subscriber(new_triggers: set[str]):
        """Simulate a working subscriber."""
        trigger_events.append(new_triggers)

    ws_client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "labs", {})
    await ws_client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "automation",
            "preview_feature": "new_triggers_conditions",
            "enabled": True,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    await hass.async_block_till_done()

    trigger.async_subscribe_platform_events(hass, good_subscriber)

    assert await async_setup_component(hass, "light", {})
    await hass.async_block_till_done()
    assert trigger_events == []


@pytest.mark.parametrize(
    ("trigger_options", "expected_result"),
    [
        # Test validating climate.target_temperature_changed
        # Valid: no limits at all
        (
            {"threshold": {"type": "any"}},
            does_not_raise(),
        ),
        # Valid: numerical limits
        (
            {"threshold": {"type": "above", "value": {"number": 10}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "below", "value": {"number": 90}}},
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        # Valid: entity references
        (
            {"threshold": {"type": "above", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "below", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Valid: Mix of numerical limits and entity references
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Test invalid configurations
        (
            # Missing threshold type
            {},
            pytest.raises(vol.Invalid),
        ),
        (
            # Invalid threshold type
            {"threshold": {"type": "invalid_type"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must be valid entity id
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "cat"},
                    "value_max": {"entity": "dog"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        (
            # Above must be smaller than below
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 90},
                    "value_max": {"number": 10},
                }
            },
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_numerical_state_attribute_changed_trigger_config_validation(
    hass: HomeAssistant,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test numerical state attribute change trigger config validation."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "test_trigger": make_entity_numerical_state_changed_trigger(
                {"test": DomainSpec(value_source="test_attribute")}
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": "test.test_trigger",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


def _make_with_unit_changed_trigger_class() -> type[
    EntityNumericalStateChangedTriggerWithUnitBase
]:
    """Create a concrete WithUnit changed trigger class for testing."""

    class _TestChangedTrigger(
        EntityNumericalStateChangedTriggerWithUnitBase,
    ):
        _base_unit = UnitOfTemperature.CELSIUS
        _domain_specs = {"test": DomainSpec(value_source="test_attribute")}
        _unit_converter = TemperatureConverter

    return _TestChangedTrigger


@pytest.mark.parametrize(
    ("trigger_options", "expected_result"),
    [
        # Valid: no limits at all
        (
            {"threshold": {"type": "any"}},
            does_not_raise(),
        ),
        # Valid: unit provided with numerical limits
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 10, "unit_of_measurement": "°C"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "below",
                    "value": {"number": 90, "unit_of_measurement": "°F"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10, "unit_of_measurement": "°C"},
                    "value_max": {"number": 90, "unit_of_measurement": "°F"},
                }
            },
            does_not_raise(),
        ),
        # Valid: no unit needed when using entity references
        (
            {"threshold": {"type": "above", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "below", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Valid: unit only needed for numerical limits, not entity references
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"number": 90, "unit_of_measurement": "°C"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10, "unit_of_measurement": "°C"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Invalid: missing threshold type
        (
            {},
            pytest.raises(vol.Invalid),
        ),
        # Invalid: invalid threshold type
        (
            {"threshold": {"type": "invalid_type"}},
            pytest.raises(vol.Invalid),
        ),
        # Invalid: numerical limit without unit
        (
            {"threshold": {"type": "above", "value": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            {"threshold": {"type": "below", "value": {"number": 90}}},
            pytest.raises(vol.Invalid),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 90},
                    "value_max": {"number": 90},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: one numerical limit without unit (other is entity)
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"number": 90},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: invalid unit value
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 10, "unit_of_measurement": "invalid_unit"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: Must use valid entity id
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "cat"},
                    "value_max": {"entity": "dog"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: above must be smaller than below
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 90, "unit_of_measurement": "°C"},
                    "value_max": {"number": 10, "unit_of_measurement": "°F"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_numerical_state_attribute_changed_with_unit_trigger_config_validation(
    hass: HomeAssistant,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test numerical state attribute change with unit trigger config validation."""
    trigger_cls = _make_with_unit_changed_trigger_class()

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {"test_trigger": trigger_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": "test.test_trigger",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


async def test_numerical_state_attribute_changed_error_handling(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test numerical state attribute change error handling."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "attribute_changed": make_entity_numerical_state_changed_trigger(
                {"test": DomainSpec(value_source="test_attribute")}
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    hass.states.async_set("test.test_entity", "on", {"test_attribute": 20})

    options = {
        CONF_OPTIONS: {
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.above"},
                "value_max": {"entity": "sensor.below"},
            }
        }
    }

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "test.attribute_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )

    assert len(service_calls) == 0

    # Test the trigger works
    hass.states.async_set("sensor.above", "10")
    hass.states.async_set("sensor.below", "90")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger fires again when still within limits
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 51})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger does not fire when the from-state is unknown or unavailable
    for from_state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        hass.states.async_set("test.test_entity", from_state)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is outside the limits
    for value in (5, 95):
        hass.states.async_set("test.test_entity", "on", {"test_attribute": value})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is missing
    hass.states.async_set("test.test_entity", "on", {})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is invalid
    for value in ("cat", None):
        hass.states.async_set("test.test_entity", "on", {"test_attribute": value})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor does not exist
    hass.states.async_remove("sensor.above")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set("sensor.above", invalid_value)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Reset the above sensor state to a valid numeric value
    hass.states.async_set("sensor.above", "10")

    # Test the trigger does not fire when the below sensor does not exist
    hass.states.async_remove("sensor.below")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the below sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set("sensor.below", invalid_value)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0


async def test_numerical_state_attribute_changed_entity_limit_unit_validation(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that entity limits with wrong unit are rejected."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "attribute_changed": make_entity_numerical_state_changed_trigger(
                {"test": DomainSpec(value_source="test_attribute")},
                valid_unit="%",
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    hass.states.async_set("test.test_entity", "on", {"test_attribute": 20})

    options = {
        CONF_OPTIONS: {
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.above"},
                "value_max": {"entity": "sensor.below"},
            }
        }
    }

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "test.attribute_changed",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )

    assert len(service_calls) == 0

    # Test the trigger works with correct unit on limit entities
    hass.states.async_set("sensor.above", "10", {ATTR_UNIT_OF_MEASUREMENT: "%"})
    hass.states.async_set("sensor.below", "90", {ATTR_UNIT_OF_MEASUREMENT: "%"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger does not fire when the above sensor has wrong unit
    hass.states.async_set("sensor.above", "10", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor has no unit
    hass.states.async_set("sensor.above", "10")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Reset the above sensor to correct unit
    hass.states.async_set("sensor.above", "10", {ATTR_UNIT_OF_MEASUREMENT: "%"})

    # Test the trigger does not fire when the below sensor has wrong unit
    hass.states.async_set("sensor.below", "90", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the below sensor has no unit
    hass.states.async_set("sensor.below", "90")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_numerical_state_attribute_changed_with_unit_error_handling(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test numerical state attribute change with unit conversion error handling."""
    trigger_cls = _make_with_unit_changed_trigger_class()

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {"attribute_changed": trigger_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    # Entity reports in °F, trigger configured in °C with above 20°C, below 30°C
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 68,  # 68°F = 20°C
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "test.attribute_changed",
                        CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                        CONF_OPTIONS: {
                            "threshold": {
                                "type": "between",
                                "value_min": {
                                    "number": 20,
                                    "unit_of_measurement": "°C",
                                },
                                "value_max": {
                                    "number": 30,
                                    "unit_of_measurement": "°C",
                                },
                            }
                        },
                    },
                    "action": {
                        "service": "test.numerical_automation",
                        "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                    },
                },
                {
                    "trigger": {
                        CONF_PLATFORM: "test.attribute_changed",
                        CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                        CONF_OPTIONS: {
                            "threshold": {
                                "type": "between",
                                "value_min": {"entity": "sensor.above"},
                                "value_max": {"entity": "sensor.below"},
                            }
                        },
                    },
                    "action": {
                        "service": "test.entity_automation",
                        "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                    },
                },
            ]
        },
    )

    assert len(service_calls) == 0

    # 77°F = 25°C, within range (above 20, below 30) - should trigger numerical
    # Entity automation won't trigger because sensor.above/below don't exist yet
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 77,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].service == "numerical_automation"
    service_calls.clear()

    # 59°F = 15°C, below 20°C - should NOT trigger
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 59,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # 95°F = 35°C, above 30°C - should NOT trigger
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 95,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Set up entity limits referencing sensors that report in °F
    hass.states.async_set(
        "sensor.above",
        "68",  # 68°F = 20°C
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    hass.states.async_set(
        "sensor.below",
        "86",  # 86°F = 30°C
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )

    # 77°F = 25°C, between 20°C and 30°C - should trigger both automations
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 77,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert {call.service for call in service_calls} == {
        "numerical_automation",
        "entity_automation",
    }
    service_calls.clear()

    # Test the trigger does not fire when the attribute value is missing
    hass.states.async_set("test.test_entity", "on", {})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is invalid
    for value in ("cat", None):
        hass.states.async_set(
            "test.test_entity",
            "on",
            {
                "test_attribute": value,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
            },
        )
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the unit is incompatible
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 50,
            ATTR_UNIT_OF_MEASUREMENT: "invalid_unit",
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor does not exist
    hass.states.async_remove("sensor.above")
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": None,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {"test_attribute": 50, ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set(
            "sensor.above",
            invalid_value,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
        )
        hass.states.async_set(
            "test.test_entity",
            "on",
            {
                "test_attribute": None,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
            },
        )
        hass.states.async_set(
            "test.test_entity",
            "on",
            {
                "test_attribute": 50,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
            },
        )
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the above sensor's unit is incompatible
    hass.states.async_set(
        "sensor.above",
        "68",  # 68°F = 20°C
        {ATTR_UNIT_OF_MEASUREMENT: "invalid_unit"},
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": None,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {"test_attribute": 50, ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Reset the above sensor state to a valid numeric value
    hass.states.async_set(
        "sensor.above",
        "68",  # 68°F = 20°C
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )

    # Test the trigger does not fire when the below sensor does not exist
    hass.states.async_remove("sensor.below")
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": None,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {"test_attribute": 50, ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the below sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set("sensor.below", invalid_value)
        hass.states.async_set(
            "test.test_entity",
            "on",
            {
                "test_attribute": None,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
            },
        )
        hass.states.async_set(
            "test.test_entity",
            "on",
            {
                "test_attribute": 50,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
            },
        )
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the below sensor's unit is incompatible
    hass.states.async_set(
        "sensor.below",
        "68",  # 68°F = 20°C
        {ATTR_UNIT_OF_MEASUREMENT: "invalid_unit"},
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": None,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    hass.states.async_set(
        "test.test_entity",
        "on",
        {"test_attribute": 50, ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_options", "expected_result"),
    [
        # Valid configurations
        # Don't use the enum in tests to allow testing validation of strings when the source is JSON or YAML
        (
            {"threshold": {"type": "above", "value": {"number": 10}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "above", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "below", "value": {"number": 90}}},
            does_not_raise(),
        ),
        (
            {"threshold": {"type": "below", "value": {"entity": "sensor.test"}}},
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"number": 10},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"number": 90},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "outside",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Test verbose choose selector options
        # Test invalid configurations
        (
            # Missing threshold type
            {},
            pytest.raises(vol.Invalid),
        ),
        (
            # Missing threshold type
            {"threshold": {}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Invalid threshold type
            {"threshold": {"type": "cat"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide lower limit for ABOVE
            {"threshold": {"type": "above"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide lower limit for ABOVE
            {"threshold": {"type": "above", "value_min": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide lower limit for ABOVE
            {"threshold": {"type": "above", "value_max": {"number": 90}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper limit for BELOW
            {"threshold": {"type": "below"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper limit for BELOW
            {"threshold": {"type": "below", "value_min": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper limit for BELOW
            {"threshold": {"type": "below", "value_max": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for BETWEEN
            {"threshold": {"type": "between"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for BETWEEN
            {"threshold": {"type": "between", "value_min": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for BETWEEN
            {"threshold": {"type": "between", "value_max": {"number": 90}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for OUTSIDE
            {"threshold": {"type": "outside"}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for OUTSIDE
            {"threshold": {"type": "outside", "value_min": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must provide upper and lower limits for OUTSIDE
            {"threshold": {"type": "outside", "value_max": {"number": 90}}},
            pytest.raises(vol.Invalid),
        ),
        (
            # Must be valid entity id
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "cat"},
                    "value_max": {"entity": "dog"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        (
            # Min must be smaller than max
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 90},
                    "value_max": {"number": 10},
                }
            },
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_numerical_state_attribute_crossed_threshold_trigger_config_validation(
    hass: HomeAssistant,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test numerical state attribute change trigger config validation."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "test_trigger": make_entity_numerical_state_crossed_threshold_trigger(
                {"test": DomainSpec(value_source="test_attribute")}
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": "test.test_trigger",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


def _make_with_unit_crossed_threshold_trigger_class() -> type[
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase
]:
    """Create a concrete WithUnit crossed threshold trigger class for testing."""

    class _TestCrossedThresholdTrigger(
        EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    ):
        _base_unit = UnitOfTemperature.CELSIUS
        _domain_specs = {"test": DomainSpec(value_source="test_attribute")}
        _unit_converter = TemperatureConverter

    return _TestCrossedThresholdTrigger


@pytest.mark.parametrize(
    ("trigger_options", "expected_result"),
    [
        # Valid: unit provided with numerical limits
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {
                        "number": 10,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "below",
                    "value": {
                        "number": 90,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {
                        "number": 10,
                        "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    },
                    "value_max": {
                        "number": 90,
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    },
                }
            },
            does_not_raise(),
        ),
        # Valid: no unit needed when using entity references
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.test"},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            does_not_raise(),
        ),
        # Invalid: numerical limit without unit
        (
            {"threshold": {"type": "above", "value": {"number": 10}}},
            pytest.raises(vol.Invalid),
        ),
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"number": 90},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: one numerical limit without unit (other is entity)
        (
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"number": 10},
                    "value_max": {"entity": "sensor.test"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: invalid unit value
        (
            {
                "threshold": {
                    "type": "above",
                    "value": {"number": 10, "unit_of_measurement": "invalid_unit"},
                }
            },
            pytest.raises(vol.Invalid),
        ),
        # Invalid: missing threshold type
        (
            {},
            pytest.raises(vol.Invalid),
        ),
        # Invalid: missing threshold type
        (
            {"threshold": {}},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_numerical_state_attribute_crossed_threshold_with_unit_trigger_config_validation(
    hass: HomeAssistant,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test numerical state attribute crossed threshold with unit trigger config validation."""
    trigger_cls = _make_with_unit_crossed_threshold_trigger_class()

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {"test_trigger": trigger_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": "test.test_trigger",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


async def test_numerical_state_attribute_crossed_threshold_error_handling(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test numerical state attribute crossed threshold error handling."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
                {"test": DomainSpec(value_source="test_attribute")}
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})

    options = {
        CONF_OPTIONS: {
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.lower"},
                "value_max": {"entity": "sensor.upper"},
            }
        },
    }

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "test.crossed_threshold",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )

    assert len(service_calls) == 0

    # Test the trigger works
    hass.states.async_set("sensor.lower", "10")
    hass.states.async_set("sensor.upper", "90")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger does not fire again when still within limits
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 51})
    await hass.async_block_till_done()
    assert len(service_calls) == 0
    service_calls.clear()

    # Test the trigger does not fire when the from-state is unknown or unavailable
    for from_state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        hass.states.async_set("test.test_entity", from_state)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does fire when the attribute value is changing from None
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger does not fire when the attribute value is outside the limits
    for value in (5, 95):
        hass.states.async_set("test.test_entity", "on", {"test_attribute": value})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is missing
    hass.states.async_set("test.test_entity", "on", {})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the attribute value is invalid
    for value in ("cat", None):
        hass.states.async_set("test.test_entity", "on", {"test_attribute": value})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Test the trigger does not fire when the lower sensor does not exist
    hass.states.async_remove("sensor.lower")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the lower sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set("sensor.lower", invalid_value)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0

    # Reset the lower sensor state to a valid numeric value
    hass.states.async_set("sensor.lower", "10")

    # Test the trigger does not fire when the upper sensor does not exist
    hass.states.async_remove("sensor.upper")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the upper sensor state is not numeric
    for invalid_value in ("cat", None):
        hass.states.async_set("sensor.upper", invalid_value)
        hass.states.async_set("test.test_entity", "on", {"test_attribute": None})
        hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
        await hass.async_block_till_done()
        assert len(service_calls) == 0


async def test_numerical_state_attribute_crossed_threshold_entity_limit_unit_validation(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that entity limits with wrong unit are rejected for crossed threshold."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {
            "crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
                {"test": DomainSpec(value_source="test_attribute")},
                valid_unit="%",
            ),
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})

    options = {
        CONF_OPTIONS: {
            "threshold": {
                "type": "between",
                "value_min": {"entity": "sensor.lower"},
                "value_max": {"entity": "sensor.upper"},
            }
        },
    }

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "test.crossed_threshold",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )

    assert len(service_calls) == 0

    # Test the trigger works with correct unit on limit entities
    hass.states.async_set("sensor.lower", "10", {ATTR_UNIT_OF_MEASUREMENT: "%"})
    hass.states.async_set("sensor.upper", "90", {ATTR_UNIT_OF_MEASUREMENT: "%"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test the trigger does not fire when the lower sensor has wrong unit
    hass.states.async_set("sensor.lower", "10", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the lower sensor has no unit
    hass.states.async_set("sensor.lower", "10")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Reset the lower sensor to correct unit
    hass.states.async_set("sensor.lower", "10", {ATTR_UNIT_OF_MEASUREMENT: "%"})

    # Test the trigger does not fire when the upper sensor has wrong unit
    hass.states.async_set("sensor.upper", "90", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test the trigger does not fire when the upper sensor has no unit
    hass.states.async_set("sensor.upper", "90")
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 0})
    hass.states.async_set("test.test_entity", "on", {"test_attribute": 50})
    await hass.async_block_till_done()
    assert len(service_calls) == 0


async def test_numerical_state_attribute_crossed_threshold_with_unit_error_handling(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test numerical state attribute crossed threshold with unit conversion."""
    trigger_cls = _make_with_unit_crossed_threshold_trigger_class()

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {"crossed_threshold": trigger_cls}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    # Entity reports in °F, trigger configured in °C: above 25°C
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 68,  # 68°F = 20°C, below threshold
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )

    options = {
        CONF_OPTIONS: {
            "threshold": {
                "type": "above",
                "value": {
                    "number": 25,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                },
            }
        },
    }

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: "test.crossed_threshold",
                    CONF_TARGET: {CONF_ENTITY_ID: "test.test_entity"},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )

    assert len(service_calls) == 0

    # 80.6°F = 27°C, above 25°C threshold - should trigger
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 80.6,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Still above threshold - should NOT trigger (already crossed)
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 82,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Drop below threshold and cross again
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 68,  # 20°C, below 25°C
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 80.6,  # 27°C, above 25°C again
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    service_calls.clear()

    # Test with incompatible unit - should NOT trigger
    hass.states.async_set(
        "test.test_entity",
        "on",
        {
            "test_attribute": 50,
            ATTR_UNIT_OF_MEASUREMENT: "invalid_unit",
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0


def _make_trigger(
    hass: HomeAssistant, domain_specs: Mapping[str, DomainSpec]
) -> EntityTriggerBase:
    """Create a minimal EntityTriggerBase subclass with the given domain specs."""

    class _SimpleTrigger(EntityTriggerBase):
        """Minimal concrete trigger for testing entity_filter."""

        _domain_specs = domain_specs

        def is_valid_transition(self, from_state: State, to_state: State) -> bool:
            """Accept any transition."""
            return True

        def is_valid_state(self, state: State) -> bool:
            """Accept any state."""
            return True

    config = TriggerConfig(key="test.test_trigger", target={CONF_ENTITY_ID: []})
    return _SimpleTrigger(hass, config)


async def test_entity_filter_by_domain_only(hass: HomeAssistant) -> None:
    """Test entity_filter includes entities matching domain, excludes others."""
    trig = _make_trigger(hass, {"sensor": DomainSpec(), "switch": DomainSpec()})

    entities = {
        "sensor.temp",
        "sensor.humidity",
        "switch.light",
        "light.bedroom",
        "cover.garage",
    }
    result = trig.entity_filter(entities)
    assert result == {"sensor.temp", "sensor.humidity", "switch.light"}


async def test_entity_filter_by_device_class(hass: HomeAssistant) -> None:
    """Test entity_filter filters by device_class when specified."""
    trig = _make_trigger(hass, {"sensor": DomainSpec(device_class="humidity")})

    # Set states with device_class attributes
    hass.states.async_set("sensor.humidity_1", "50", {ATTR_DEVICE_CLASS: "humidity"})
    hass.states.async_set(
        "sensor.temperature_1", "22", {ATTR_DEVICE_CLASS: "temperature"}
    )
    hass.states.async_set("sensor.no_class", "10", {})

    entities = {"sensor.humidity_1", "sensor.temperature_1", "sensor.no_class"}
    result = trig.entity_filter(entities)
    assert result == {"sensor.humidity_1"}


async def test_entity_filter_device_class_unknown_entity(
    hass: HomeAssistant,
) -> None:
    """Test entity_filter excludes entities not in state machine or registry."""
    trig = _make_trigger(hass, {"sensor": DomainSpec(device_class="humidity")})

    # Entity not in state machine and not in entity registry -> UNDEFINED
    entities = {"sensor.nonexistent"}
    result = trig.entity_filter(entities)
    assert result == set()


async def test_entity_filter_multiple_domains_with_device_class(
    hass: HomeAssistant,
) -> None:
    """Test entity_filter with multiple domains, some with device_class filtering."""
    trig = _make_trigger(
        hass,
        {
            "climate": DomainSpec(value_source="current_humidity"),
            "sensor": DomainSpec(device_class="humidity"),
            "weather": DomainSpec(value_source="humidity"),
        },
    )

    hass.states.async_set("sensor.humidity", "60", {ATTR_DEVICE_CLASS: "humidity"})
    hass.states.async_set(
        "sensor.temperature", "20", {ATTR_DEVICE_CLASS: "temperature"}
    )
    hass.states.async_set("climate.hvac", "heat", {})
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("light.bedroom", "on", {})

    entities = {
        "sensor.humidity",
        "sensor.temperature",
        "climate.hvac",
        "weather.home",
        "light.bedroom",
    }
    result = trig.entity_filter(entities)
    # sensor.temperature excluded (wrong device_class)
    # light.bedroom excluded (no matching domain)
    assert result == {"sensor.humidity", "climate.hvac", "weather.home"}


async def test_entity_filter_no_device_class_means_match_all_in_domain(
    hass: HomeAssistant,
) -> None:
    """Test that DomainSpec without device_class matches all entities in the domain."""
    trig = _make_trigger(hass, {"cover": DomainSpec()})

    hass.states.async_set("cover.door", "open", {ATTR_DEVICE_CLASS: "door"})
    hass.states.async_set("cover.garage", "closed", {ATTR_DEVICE_CLASS: "garage"})
    hass.states.async_set("cover.plain", "open", {})

    entities = {"cover.door", "cover.garage", "cover.plain"}
    result = trig.entity_filter(entities)
    assert result == entities


@pytest.mark.parametrize(
    ("domain_specs", "to_states", "from_state", "to_state", "wrong_value_state"),
    [
        pytest.param(
            {"light": DomainSpec()},
            {"on"},
            State("light.bed", "off"),
            State("light.bed", "on"),
            State("light.bed", "off"),
            id="state_based",
        ),
        pytest.param(
            {"light": DomainSpec(value_source="color_mode")},
            {"hs"},
            State("light.bed", "on", {"color_mode": "color_temp"}),
            State("light.bed", "on", {"color_mode": "hs"}),
            State("light.bed", "on", {"color_mode": "rgb"}),
            id="attribute_based",
        ),
        pytest.param(
            "light",
            {"on"},
            State("light.bed", "off"),
            State("light.bed", "on"),
            State("light.bed", "off"),
            id="state_based_domain_string",
        ),
    ],
)
async def test_make_entity_target_state_trigger(
    hass: HomeAssistant,
    domain_specs: Mapping[str, DomainSpec] | str,
    to_states: set[str],
    from_state: State,
    to_state: State,
    wrong_value_state: State,
) -> None:
    """Test make_entity_target_state_trigger with state and attribute-based DomainSpec."""
    trigger_cls = make_entity_target_state_trigger(domain_specs, to_states=to_states)

    config = TriggerConfig(key="light.turned_on", target={"entity_id": "light.bed"})
    trig = trigger_cls(hass, config)

    # Value changed to target — valid
    assert trig.is_valid_transition(from_state, to_state)
    assert trig.is_valid_state(to_state)

    # Value did not change — not a valid transition
    assert not trig.is_valid_transition(from_state, from_state)

    # From unavailable — not valid
    unavailable = State("light.bed", STATE_UNAVAILABLE, {})
    assert not trig.is_valid_transition(unavailable, to_state)

    # Value not in to_states — not valid
    assert not trig.is_valid_state(wrong_value_state)


@pytest.mark.parametrize(
    (
        "domain_specs",
        "from_states",
        "to_states",
        "from_state",
        "to_state",
        "wrong_from",
        "wrong_to",
    ),
    [
        pytest.param(
            {"climate": DomainSpec()},
            {"off"},
            {"heat"},
            State("climate.living", "off"),
            State("climate.living", "heat"),
            State("climate.living", "cool"),
            State("climate.living", "cool"),
            id="state_based",
        ),
        pytest.param(
            {"climate": DomainSpec(value_source="hvac_action")},
            {"idle"},
            {"heating"},
            State("climate.living", "heat", {"hvac_action": "idle"}),
            State("climate.living", "heat", {"hvac_action": "heating"}),
            State("climate.living", "heat", {"hvac_action": "heating"}),
            State("climate.living", "heat", {"hvac_action": "idle"}),
            id="attribute_based",
        ),
    ],
)
async def test_make_entity_transition_trigger(
    hass: HomeAssistant,
    domain_specs: Mapping[str, DomainSpec],
    from_states: set[str],
    to_states: set[str],
    from_state: State,
    to_state: State,
    wrong_from: State,
    wrong_to: State,
) -> None:
    """Test make_entity_transition_trigger with state and attribute-based DomainSpec."""
    trigger_cls = make_entity_transition_trigger(
        domain_specs, from_states=from_states, to_states=to_states
    )

    config = TriggerConfig(
        key="climate.hvac_action", target={"entity_id": "climate.living"}
    )
    trig = trigger_cls(hass, config)

    # Valid transition
    assert trig.is_valid_transition(from_state, to_state)
    assert trig.is_valid_state(to_state)

    # Wrong origin (not in from_states)
    assert not trig.is_valid_transition(wrong_from, to_state)

    # Wrong target (not in to_states)
    assert not trig.is_valid_state(wrong_to)

    # No change in tracked value — not a valid transition
    assert not trig.is_valid_transition(from_state, from_state)

    # From unavailable — not valid
    unavailable = State("climate.living", STATE_UNAVAILABLE, {})
    assert not trig.is_valid_transition(unavailable, to_state)


@pytest.mark.parametrize(
    ("domain_specs", "origin", "from_state", "to_state", "wrong_from"),
    [
        pytest.param(
            {"climate": DomainSpec()},
            "off",
            State("climate.living", "off"),
            State("climate.living", "heat"),
            State("climate.living", "cool"),
            id="state_based",
        ),
        pytest.param(
            {"climate": DomainSpec(value_source="hvac_action")},
            "idle",
            State("climate.living", "heat", {"hvac_action": "idle"}),
            State("climate.living", "heat", {"hvac_action": "heating"}),
            State("climate.living", "heat", {"hvac_action": "heating"}),
            id="attribute_based",
        ),
    ],
)
async def test_make_entity_origin_state_trigger(
    hass: HomeAssistant,
    domain_specs: Mapping[str, DomainSpec],
    origin: str,
    from_state: State,
    to_state: State,
    wrong_from: State,
) -> None:
    """Test make_entity_origin_state_trigger with state and attribute-based DomainSpec."""
    trigger_cls = make_entity_origin_state_trigger(domain_specs, from_state=origin)

    config = TriggerConfig(
        key="climate.started_heating", target={"entity_id": "climate.living"}
    )
    trig = trigger_cls(hass, config)

    # Valid: changed from expected origin to something else
    assert trig.is_valid_transition(from_state, to_state)
    assert trig.is_valid_state(to_state)

    # Wrong origin (not the expected from_state)
    assert not trig.is_valid_transition(wrong_from, to_state)

    # No change in tracked value — not a valid transition
    assert not trig.is_valid_transition(from_state, from_state)

    # To-state still matches from_state — not valid
    assert not trig.is_valid_state(from_state)
