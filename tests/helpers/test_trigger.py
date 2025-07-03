"""The tests for the trigger helper."""

import io
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch

import pytest
from pytest_unordered import unordered
import voluptuous as vol

from homeassistant.components.sun import DOMAIN as DOMAIN_SUN
from homeassistant.components.system_health import DOMAIN as DOMAIN_SYSTEM_HEALTH
from homeassistant.components.tag import DOMAIN as DOMAIN_TAG
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
    trigger,
)
from homeassistant.helpers.trigger import (
    DATA_PLUGGABLE_ACTIONS,
    PluggableAction,
    Trigger,
    TriggerActionType,
    TriggerInfo,
    _async_get_trigger_platform,
    async_initialize_triggers,
    async_track_target_selector_state_change_event,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration, async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
)


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
        await _async_get_trigger_platform(hass, {"platform": "test.subtype"})
        assert integration_mock.call_args == call(hass, "test")


async def test_trigger_variables(hass: HomeAssistant) -> None:
    """Test trigger variables."""


async def test_if_fires_on_event(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the firing of events."""
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


async def test_platform_multiple_triggers(hass: HomeAssistant) -> None:
    """Test a trigger platform with multiple trigger."""

    class MockTrigger(Trigger):
        """Mock trigger."""

        def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
            """Initialize trigger."""

        @classmethod
        async def async_validate_trigger_config(
            cls, hass: HomeAssistant, config: ConfigType
        ) -> ConfigType:
            """Validate config."""
            return config

    class MockTrigger1(MockTrigger):
        """Mock trigger 1."""

        async def async_attach_trigger(
            self,
            action: TriggerActionType,
            trigger_info: TriggerInfo,
        ) -> CALLBACK_TYPE:
            """Attach a trigger."""
            action({"trigger": "test_trigger_1"})

    class MockTrigger2(MockTrigger):
        """Mock trigger 2."""

        async def async_attach_trigger(
            self,
            action: TriggerActionType,
            trigger_info: TriggerInfo,
        ) -> CALLBACK_TYPE:
            """Attach a trigger."""
            action({"trigger": "test_trigger_2"})

    async def async_get_triggers(
        hass: HomeAssistant,
    ) -> dict[str, type[Trigger]]:
        return {
            "test": MockTrigger1,
            "test.trig_2": MockTrigger2,
        }

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))

    config_1 = [{"platform": "test"}]
    config_2 = [{"platform": "test.trig_2"}]
    config_3 = [{"platform": "test.unknown_trig"}]
    assert await async_validate_trigger_config(hass, config_1) == config_1
    assert await async_validate_trigger_config(hass, config_2) == config_2
    with pytest.raises(
        vol.Invalid, match="Invalid trigger 'test.unknown_trig' specified"
    ):
        await async_validate_trigger_config(hass, config_3)

    log_cb = MagicMock()

    action_calls = []

    @callback
    def cb_action(*args):
        action_calls.append([*args])

    await async_initialize_triggers(hass, config_1, cb_action, "test", "", log_cb)
    assert action_calls == [[{"trigger": "test_trigger_1"}]]
    action_calls.clear()

    await async_initialize_triggers(hass, config_2, cb_action, "test", "", log_cb)
    assert action_calls == [[{"trigger": "test_trigger_2"}]]
    action_calls.clear()

    with pytest.raises(KeyError):
        await async_initialize_triggers(hass, config_3, cb_action, "test", "", log_cb)


@pytest.mark.parametrize(
    "sun_trigger_descriptions",
    [
        """
        sun:
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
        sun:
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
    hass: HomeAssistant, sun_trigger_descriptions: str
) -> None:
    """Test async_get_all_descriptions."""
    tag_trigger_descriptions = """
        tag: {}
        """

    assert await async_setup_component(hass, DOMAIN_SUN, {})
    assert await async_setup_component(hass, DOMAIN_SYSTEM_HEALTH, {})
    await hass.async_block_till_done()

    def _load_yaml(fname, secrets=None):
        if fname.endswith("sun/triggers.yaml"):
            trigger_descriptions = sun_trigger_descriptions
        elif fname.endswith("tag/triggers.yaml"):
            trigger_descriptions = tag_trigger_descriptions
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
    assert proxy_load_triggers_files.mock_calls[0][1][1] == unordered(
        [
            await async_get_integration(hass, DOMAIN_SUN),
        ]
    )

    # system_health does not have triggers and should not be in descriptions
    assert descriptions == {
        DOMAIN_SUN: {
            "fields": {
                "event": {
                    "example": "sunrise",
                    "selector": {"select": {"options": ["sunrise", "sunset"]}},
                },
                "offset": {"selector": {"time": None}},
            }
        }
    }

    # Verify the cache returns the same object
    assert await trigger.async_get_all_descriptions(hass) is descriptions

    # Load the tag integration and check a new cache object is created
    assert await async_setup_component(hass, DOMAIN_TAG, {})
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
    assert new_descriptions == {
        DOMAIN_SUN: {
            "fields": {
                "event": {
                    "example": "sunrise",
                    "selector": {"select": {"options": ["sunrise", "sunset"]}},
                },
                "offset": {"selector": {"time": None}},
            }
        },
        DOMAIN_TAG: {
            "fields": {},
        },
    }

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
    assert await async_setup_component(hass, DOMAIN_SUN, {})
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

    assert descriptions == {DOMAIN_SUN: None}

    assert expected_message in caplog.text


async def test_async_get_all_descriptions_with_bad_description(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_get_all_descriptions."""
    sun_service_descriptions = """
        sun:
          fields: not_a_dict
    """

    assert await async_setup_component(hass, DOMAIN_SUN, {})
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

    assert descriptions == {DOMAIN_SUN: None}

    assert (
        "Unable to parse triggers.yaml for the sun integration: "
        "expected a dictionary for dictionary value @ data['sun']['fields']"
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


async def test_async_track_target_selector_state_change_event_empty_selector(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_track_target_selector_state_change_event with empty selector."""
    calls = []

    @callback
    def state_change_callback(event):
        """Handle state change events."""
        calls.append(event)

    unsub = async_track_target_selector_state_change_event(
        hass, {}, state_change_callback
    )

    assert "Target selector {} does not have any selectors defined" in caplog.text

    # Test that no state changes are tracked
    hass.states.async_set("light.test", "on")
    await hass.async_block_till_done()

    assert len(calls) == 0

    unsub()


async def test_async_track_target_selector_state_change_event(
    hass: HomeAssistant,
) -> None:
    """Test async_track_target_selector_state_change_event with multiple targets."""
    calls = []

    @callback
    def state_change_callback(event):
        """Handle state change events."""
        calls.append(event)

    async def set_state(entity_id, state):
        """Set the state of an entity."""
        hass.states.async_set(entity_id, state)
        await hass.async_block_till_done()

    def assert_entity_calls_and_reset(entity_id: str) -> None:
        assert len(calls) == 1
        assert calls[0].data["entity_id"] == entity_id
        calls.clear()

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "device_1")},
    )

    untargeted_device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "area_device")},
    )

    entity_reg = er.async_get(hass)
    device_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="device_light",
        device_id=device_entry.id,
    ).entity_id

    untargeted_device_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="area_device_light",
        device_id=untargeted_device_entry.id,
    ).entity_id

    untargeted_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="untargeted_light",
    ).entity_id

    targeted_entity = "light.test_light"

    for entity_id in (targeted_entity, device_entity, untargeted_entity):
        hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()

    label = lr.async_get(hass).async_create("Test Label").name
    area = ar.async_get(hass).async_create("Test Area").id
    floor = fr.async_get(hass).async_create("Test Floor").floor_id

    selector_config = {
        ATTR_ENTITY_ID: targeted_entity,
        ATTR_DEVICE_ID: device_entry.id,
        ATTR_AREA_ID: area,
        ATTR_FLOOR_ID: floor,
        ATTR_LABEL_ID: label,
    }
    unsub = async_track_target_selector_state_change_event(
        hass, selector_config, state_change_callback
    )

    # Test directly targeted entity and device
    await set_state(targeted_entity, STATE_ON)
    await set_state(device_entity, STATE_ON)

    assert len(calls) == 2
    assert calls[0].data["entity_id"] == targeted_entity
    assert calls[0].data["old_state"].state == STATE_OFF
    assert calls[0].data["new_state"].state == STATE_ON
    assert calls[1].data["entity_id"] == device_entity
    assert calls[1].data["old_state"].state == STATE_OFF
    assert calls[1].data["new_state"].state == STATE_ON
    calls.clear()

    # Add new entity to the targeted device -> should trigger on state change
    device_entity_2 = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="device_light_2",
        device_id=device_entry.id,
    ).entity_id
    await hass.async_block_till_done()

    await set_state(device_entity_2, STATE_ON)

    assert_entity_calls_and_reset(device_entity_2)

    # Test untargeted entity -> should not trigger
    await set_state(untargeted_entity, STATE_ON)

    assert len(calls) == 0
    calls.clear()

    # Add label to untargeted entity -> should trigger now
    entity_reg.async_update_entity(untargeted_entity, labels={label})
    await hass.async_block_till_done()
    await set_state(untargeted_entity, STATE_OFF)

    assert_entity_calls_and_reset(untargeted_entity)

    # Remove label from untargeted entity -> should not trigger anymore
    entity_reg.async_update_entity(untargeted_entity, labels={})
    await hass.async_block_till_done()
    await set_state(untargeted_entity, STATE_ON)
    await set_state(untargeted_entity, STATE_OFF)

    assert len(calls) == 0

    # Add area to untargeted entity -> should trigger now
    entity_reg.async_update_entity(untargeted_entity, area_id=area)
    await hass.async_block_till_done()
    await set_state(untargeted_entity, STATE_ON)

    assert_entity_calls_and_reset(untargeted_entity)

    # Remove area from untargeted entity -> should not trigger anymore
    entity_reg.async_update_entity(untargeted_entity, area_id=None)
    await hass.async_block_till_done()
    await set_state(untargeted_entity, STATE_ON)
    await set_state(untargeted_entity, STATE_OFF)

    assert len(calls) == 0

    # Add area to untargeted device -> should trigger on state change
    device_reg.async_update_device(untargeted_device_entry.id, area_id=area)
    await hass.async_block_till_done()

    await set_state(untargeted_device_entity, STATE_ON)

    assert_entity_calls_and_reset(untargeted_device_entity)

    # Remove area from untargeted device -> should not trigger anymore
    device_reg.async_update_device(untargeted_device_entry.id, area_id=None)
    await hass.async_block_till_done()
    await set_state(untargeted_device_entity, STATE_OFF)
    await set_state(untargeted_device_entity, STATE_ON)

    assert len(calls) == 0

    # Set the untargeted area on the untargeted entity -> should not trigger
    untracked_area = ar.async_get(hass).async_create("Untargeted Area").id
    entity_reg.async_update_entity(untargeted_entity, area_id=untracked_area)
    await hass.async_block_till_done()

    await set_state(untargeted_entity, STATE_ON)
    assert len(calls) == 0

    # Set targeted floor on the untargeted area -> should trigger now
    ar.async_get(hass).async_update(untracked_area, floor_id=floor)
    await hass.async_block_till_done()

    await set_state(untargeted_entity, STATE_OFF)
    assert_entity_calls_and_reset(untargeted_entity)

    # Remove untargeted area from targeted floor -> should not trigger anymore
    ar.async_get(hass).async_update(untracked_area, floor_id=None)
    await hass.async_block_till_done()

    await set_state(untargeted_entity, STATE_ON)
    await set_state(untargeted_entity, STATE_OFF)
    assert len(calls) == 0

    # After unsubscribing, changes should not trigger
    unsub()

    for entity_id in (targeted_entity, device_entity, untargeted_entity):
        await set_state(entity_id, STATE_OFF)
        await set_state(entity_id, STATE_ON)
    assert len(calls) == 0
