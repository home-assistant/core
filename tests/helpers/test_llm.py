"""Tests for the llm helpers."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import calendar, todo
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import async_register_timer_handler
from homeassistant.components.script.config import ScriptConfig
from homeassistant.core import Context, HomeAssistant, State, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
    llm,
    selector,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from tests.common import MockConfigEntry, async_mock_service


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return tool input context."""
    return llm.LLMContext(
        platform="",
        context=None,
        user_prompt=None,
        language=None,
        assistant=None,
        device_id=None,
    )


class MyAPI(llm.API):
    """Test API."""

    prompt: str = ""
    tools: list[llm.Tool] = []

    async def async_get_api_instance(self, _: llm.ToolInput) -> llm.APIInstance:
        """Return a list of tools."""
        return llm.APIInstance(self, self.prompt, llm_context, self.tools)


async def test_get_api_no_existing(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting an llm api where no config exists."""
    with pytest.raises(HomeAssistantError):
        await llm.async_get_api(hass, "non-existing", llm_context)


async def test_register_api(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test registering an llm api."""

    api = MyAPI(hass=hass, id="test", name="Test")
    llm.async_register_api(hass, api)

    instance = await llm.async_get_api(hass, "test", llm_context)
    assert instance.api is api
    assert api in llm.async_get_apis(hass)

    with pytest.raises(HomeAssistantError):
        llm.async_register_api(hass, api)


async def test_unregister_api(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test unregistering an llm api."""

    unreg = llm.async_register_api(hass, MyAPI(hass=hass, id="test", name="Test"))
    assert await llm.async_get_api(hass, "test", llm_context)
    unreg()
    with pytest.raises(HomeAssistantError):
        assert await llm.async_get_api(hass, "test", llm_context)


async def test_reregister_api(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test unregistering an llm api then re-registering with the same id."""

    unreg = llm.async_register_api(hass, MyAPI(hass=hass, id="test", name="Test"))
    assert await llm.async_get_api(hass, "test", llm_context)
    unreg()
    llm.async_register_api(hass, MyAPI(hass=hass, id="test", name="Test"))
    assert await llm.async_get_api(hass, "test", llm_context)


async def test_unregister_twice(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test unregistering an llm api twice."""

    unreg = llm.async_register_api(hass, MyAPI(hass=hass, id="test", name="Test"))
    assert await llm.async_get_api(hass, "test", llm_context)
    unreg()

    # Unregistering twice is a bug that should not happen
    with pytest.raises(KeyError):
        unreg()


async def test_multiple_apis(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test registering multiple APIs."""

    unreg1 = llm.async_register_api(hass, MyAPI(hass=hass, id="test-1", name="Test 1"))
    llm.async_register_api(hass, MyAPI(hass=hass, id="test-2", name="Test 2"))

    # Verify both Apis are registered
    assert await llm.async_get_api(hass, "test-1", llm_context)
    assert await llm.async_get_api(hass, "test-2", llm_context)

    # Unregister and verify only one is left
    unreg1()

    with pytest.raises(HomeAssistantError):
        assert await llm.async_get_api(hass, "test-1", llm_context)

    assert await llm.async_get_api(hass, "test-2", llm_context)


async def test_call_tool_no_existing(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test calling an llm tool where no config exists."""
    instance = await llm.async_get_api(hass, "assist", llm_context)
    with pytest.raises(HomeAssistantError):
        await instance.async_call_tool(
            llm.ToolInput("test_tool", {}),
        )


async def test_assist_api(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test Assist API."""
    assert await async_setup_component(hass, "homeassistant", {})

    entity_registry.async_get_or_create(
        "light",
        "kitchen",
        "mock-id-kitchen",
        original_name="Kitchen",
        suggested_object_id="kitchen",
    ).write_unavailable_state(hass)

    test_context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=test_context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )
    schema = {
        vol.Optional("area"): cv.string,
        vol.Optional("floor"): cv.string,
        vol.Optional("preferred_area_id"): cv.string,
        vol.Optional("preferred_floor_id"): cv.string,
    }

    class MyIntentHandler(intent.IntentHandler):
        intent_type = "test_intent"
        slot_schema = schema
        platforms = set()  # Match none

    intent_handler = MyIntentHandler()

    intent.async_register(hass, intent_handler)

    assert len(llm.async_get_apis(hass)) == 1
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert [tool.name for tool in api.tools] == ["GetLiveContext"]

    # Match all
    intent_handler.platforms = None

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert [tool.name for tool in api.tools] == ["test_intent", "GetLiveContext"]

    # Match specific domain
    intent_handler.platforms = {"light"}

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert len(api.tools) == 2
    tool = api.tools[0]
    assert tool.name == "test_intent"
    assert tool.description == "Execute Home Assistant test_intent intent"
    assert tool.parameters == vol.Schema(
        {
            vol.Optional("area"): cv.string,
            vol.Optional("floor"): cv.string,
            # No preferred_area_id, preferred_floor_id
        }
    )
    assert str(tool) == "<IntentTool - test_intent>"

    assert test_context.json_fragment  # To reproduce an error case in tracing
    intent_response = intent.IntentResponse("*")
    intent_response.async_set_states(
        [State("light.matched", "on")], [State("light.unmatched", "on")]
    )
    intent_response.async_set_speech("Some speech")
    intent_response.async_set_card("Card title", "card content")
    intent_response.async_set_speech_slots({"hello": 1})
    intent_response.async_set_reprompt("Do it again")
    tool_input = llm.ToolInput(
        tool_name="test_intent",
        tool_args={"area": "kitchen", "floor": "ground_floor"},
    )

    with patch(
        "homeassistant.helpers.intent.async_handle", return_value=intent_response
    ) as mock_intent_handle:
        response = await api.async_call_tool(tool_input)

    mock_intent_handle.assert_awaited_once_with(
        hass=hass,
        platform="test_platform",
        intent_type="test_intent",
        slots={
            "area": {"value": "kitchen"},
            "floor": {"value": "ground_floor"},
        },
        text_input="test_text",
        context=test_context,
        language="*",
        assistant="conversation",
        device_id=None,
    )
    assert response == {
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "reprompt": {
            "plain": {
                "extra_data": None,
                "reprompt": "Do it again",
            },
        },
        "response_type": "action_done",
        "speech": {
            "plain": {
                "extra_data": None,
                "speech": "Some speech",
            },
        },
        "speech_slots": {
            "hello": 1,
        },
    }

    # Call with a device/area/floor
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "1234")},
        suggested_area="Test Area",
    )
    area = area_registry.async_get_area_by_name("Test Area")
    floor = floor_registry.async_create("2")
    area_registry.async_update(area.id, floor_id=floor.floor_id)
    llm_context.device_id = device.id

    with patch(
        "homeassistant.helpers.intent.async_handle", return_value=intent_response
    ) as mock_intent_handle:
        response = await api.async_call_tool(tool_input)

    mock_intent_handle.assert_awaited_once_with(
        hass=hass,
        platform="test_platform",
        intent_type="test_intent",
        slots={
            "area": {"value": "kitchen"},
            "floor": {"value": "ground_floor"},
            "preferred_area_id": {"value": area.id},
            "preferred_floor_id": {"value": floor.floor_id},
        },
        text_input="test_text",
        context=test_context,
        language="*",
        assistant="conversation",
        device_id=device.id,
    )
    assert response == {
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "response_type": "action_done",
        "reprompt": {
            "plain": {
                "extra_data": None,
                "reprompt": "Do it again",
            },
        },
        "speech": {
            "plain": {
                "extra_data": None,
                "speech": "Some speech",
            },
        },
        "speech_slots": {
            "hello": 1,
        },
    }


async def test_assist_api_get_timer_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting timer tools with Assist API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    api = await llm.async_get_api(hass, "assist", llm_context)

    assert "HassStartTimer" not in [tool.name for tool in api.tools]

    llm_context.device_id = "test_device"

    async_register_timer_handler(hass, "test_device", lambda *args: None)

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert "HassStartTimer" in [tool.name for tool in api.tools]


async def test_assist_api_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting timer tools with Assist API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})

    llm_context.device_id = "test_device"

    async_register_timer_handler(hass, "test_device", lambda *args: None)

    class MyIntentHandler(intent.IntentHandler):
        intent_type = "Super crazy intent with unique nåme"
        description = "my intent handler"

    intent.async_register(hass, MyIntentHandler())

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert [tool.name for tool in api.tools] == [
        "HassTurnOn",
        "HassTurnOff",
        "HassSetPosition",
        "HassStartTimer",
        "HassCancelTimer",
        "HassCancelAllTimers",
        "HassIncreaseTimer",
        "HassDecreaseTimer",
        "HassPauseTimer",
        "HassUnpauseTimer",
        "HassTimerStatus",
        "Super_crazy_intent_with_unique_name",
    ]


async def test_assist_api_description(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test intent description with Assist API."""

    class MyIntentHandler(intent.IntentHandler):
        intent_type = "test_intent"
        description = "my intent handler"

    intent.async_register(hass, MyIntentHandler())

    assert len(llm.async_get_apis(hass)) == 1
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert len(api.tools) == 1
    tool = api.tools[0]
    assert tool.name == "test_intent"
    assert tool.description == "my intent handler"


async def test_assist_api_prompt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test prompt for the assist API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.api_prompt == (
        "Only if the user wants to control a device, tell them to expose entities to their "
        "voice assistant in Home Assistant."
    )

    # Expose entities

    # Create a script with a unique ID
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "description": "This is a test script",
                    "sequence": [],
                    "fields": {
                        "beer": {"description": "Number of beers"},
                        "wine": {},
                    },
                },
                "script_with_no_fields": {
                    "description": "This is another test script",
                    "sequence": [],
                },
            }
        },
    )
    async_expose_entity(hass, "conversation", "script.test_script", True)
    async_expose_entity(hass, "conversation", "script.script_with_no_fields", True)

    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "1234")},
        suggested_area="Test Area",
    )
    area = area_registry.async_get_area_by_name("Test Area")
    area_registry.async_update(area.id, aliases=["Alternative name"])
    entry1 = entity_registry.async_get_or_create(
        "light",
        "kitchen",
        "mock-id-kitchen",
        original_name="Kitchen",
        suggested_object_id="kitchen",
    )
    entry2 = entity_registry.async_get_or_create(
        "light",
        "living_room",
        "mock-id-living-room",
        original_name="Living Room",
        suggested_object_id="living_room",
        device_id=device.id,
    )
    hass.states.async_set(
        entry1.entity_id,
        "on",
        {"friendly_name": "Kitchen", "temperature": Decimal("0.9"), "humidity": 65},
    )
    hass.states.async_set(entry2.entity_id, "on", {"friendly_name": "Living Room"})

    def create_entity(
        device: dr.DeviceEntry, write_state=True, aliases: set[str] | None = None
    ) -> None:
        """Create an entity for a device and track entity_id."""
        entity = entity_registry.async_get_or_create(
            "light",
            "test",
            device.id,
            device_id=device.id,
            original_name=str(device.name or "Unnamed Device"),
            suggested_object_id=str(device.name or "unnamed_device"),
        )
        if aliases:
            entity_registry.async_update_entity(entity.entity_id, aliases=aliases)
        if write_state:
            entity.write_unavailable_state(hass)

    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "1234")},
            name="Test Device",
            manufacturer="Test Manufacturer",
            model="Test Model",
            suggested_area="Test Area",
        ),
        aliases={"my test light"},
    )
    for i in range(3):
        create_entity(
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={("test", f"{i}abcd")},
                name="Test Service",
                manufacturer="Test Manufacturer",
                model="Test Model",
                suggested_area="Test Area",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
        )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "5678")},
            name="Test Device 2",
            manufacturer="Test Manufacturer 2",
            model="Device 2",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876")},
            name="Test Device 3",
            manufacturer="Test Manufacturer 3",
            model="Test Model 3A",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "qwer")},
            name="Test Device 4",
            suggested_area="Test Area 2",
        )
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "9876-disabled")},
        name="Test Device 3 - disabled",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_registry.async_update_device(
        device2.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    create_entity(device2, False)
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876-no-name")},
            manufacturer="Test Manufacturer NoName",
            model="Test Model NoName",
            suggested_area="Test Area 2",
        )
    )
    create_entity(
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={("test", "9876-integer-values")},
            name=1,
            manufacturer=2,
            model=3,
            suggested_area="Test Area 2",
        )
    )
    exposed_entities_prompt = """Live Context: An overview of the areas and the devices in this smart home:
- names: '1'
  domain: light
  state: unavailable
  areas: Test Area 2
- names: Kitchen
  domain: light
  state: 'on'
  attributes:
    temperature: '0.9'
    humidity: '65'
- names: Living Room
  domain: light
  state: 'on'
  areas: Test Area, Alternative name
- names: Test Device, my test light
  domain: light
  state: unavailable
  areas: Test Area, Alternative name
- names: Test Device 2
  domain: light
  state: unavailable
  areas: Test Area 2
- names: Test Device 3
  domain: light
  state: unavailable
  areas: Test Area 2
- names: Test Device 4
  domain: light
  state: unavailable
  areas: Test Area 2
- names: Test Service
  domain: light
  state: unavailable
  areas: Test Area, Alternative name
- names: Test Service
  domain: light
  state: unavailable
  areas: Test Area, Alternative name
- names: Test Service
  domain: light
  state: unavailable
  areas: Test Area, Alternative name
- names: Unnamed Device
  domain: light
  state: unavailable
  areas: Test Area 2
"""
    stateless_exposed_entities_prompt = """Static Context: An overview of the areas and the devices in this smart home:
- names: '1'
  domain: light
  areas: Test Area 2
- names: Kitchen
  domain: light
- names: Living Room
  domain: light
  areas: Test Area, Alternative name
- names: Test Device, my test light
  domain: light
  areas: Test Area, Alternative name
- names: Test Device 2
  domain: light
  areas: Test Area 2
- names: Test Device 3
  domain: light
  areas: Test Area 2
- names: Test Device 4
  domain: light
  areas: Test Area 2
- names: Test Service
  domain: light
  areas: Test Area, Alternative name
- names: Test Service
  domain: light
  areas: Test Area, Alternative name
- names: Test Service
  domain: light
  areas: Test Area, Alternative name
- names: Unnamed Device
  domain: light
  areas: Test Area 2
"""
    first_part_prompt = (
        "When controlling Home Assistant always call the intent tools. "
        "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
        "When controlling a device, prefer passing just name and domain. "
        "When controlling an area, prefer passing just area name and domain."
    )
    no_timer_prompt = "This device is not able to start timers."

    area_prompt = (
        "When a user asks to turn on all devices of a specific type, "
        "ask user to specify an area, unless there is only one device of that type."
    )
    dynamic_context_prompt = """You ARE equipped to answer questions about the current state of
the home using the `GetLiveContext` tool. This is a primary function. Do not state you lack the
functionality if the question requires live data.
If the user asks about device existence/type (e.g., "Do I have lights in the bedroom?"): Answer
from the static context below.
If the user asks about the CURRENT state, value, or mode (e.g., "Is the lock locked?",
"Is the fan on?", "What mode is the thermostat in?", "What is the temperature outside?"):
    1.  Recognize this requires live data.
    2.  You MUST call `GetLiveContext`. This tool will provide the needed real-time information (like temperature from the local weather, lock status, etc.).
    3.  Use the tool's response** to answer the user accurately (e.g., "The temperature outside is [value from tool].").
For general knowledge questions not about the home: Answer truthfully from internal knowledge.
"""
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{no_timer_prompt}
{dynamic_context_prompt}
{stateless_exposed_entities_prompt}"""
    )

    # Verify that the GetLiveContext tool returns the same results as the exposed_entities_prompt
    result = await api.async_call_tool(
        llm.ToolInput(tool_name="GetLiveContext", tool_args={})
    )
    assert result == {
        "success": True,
        "result": exposed_entities_prompt,
    }

    # Fake that request is made from a specific device ID with an area
    llm_context.device_id = device.id
    area_prompt = (
        "You are in area Test Area and all generic commands like 'turn on the lights' "
        "should target this area."
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{no_timer_prompt}
{dynamic_context_prompt}
{stateless_exposed_entities_prompt}"""
    )

    # Add floor
    floor = floor_registry.async_create("2")
    area_registry.async_update(area.id, floor_id=floor.floor_id)
    area_prompt = (
        "You are in area Test Area (floor 2) and all generic commands like 'turn on the lights' "
        "should target this area."
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{no_timer_prompt}
{dynamic_context_prompt}
{stateless_exposed_entities_prompt}"""
    )

    # Register device for timers
    async_register_timer_handler(hass, device.id, lambda *args: None)

    api = await llm.async_get_api(hass, "assist", llm_context)
    # The no_timer_prompt is gone
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{dynamic_context_prompt}
{stateless_exposed_entities_prompt}"""
    )


async def test_script_tool(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test ScriptTool for the assist API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )

    # Create a script with a unique ID
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "test_script": {
                    "description": "This is a test script",
                    "sequence": [
                        {"variables": {"result": {"drinks": 2}}},
                        {"stop": True, "response_variable": "result"},
                    ],
                    "fields": {
                        "beer": {"description": "Number of beers", "required": True},
                        "wine": {"selector": {"number": {"min": 0, "max": 3}}},
                        "where": {"selector": {"area": {}}},
                        "area_list": {"selector": {"area": {"multiple": True}}},
                        "floor": {"selector": {"floor": {}}},
                        "floor_list": {"selector": {"floor": {"multiple": True}}},
                        "extra_field": {"selector": {"area": {}}},
                    },
                },
                "script_with_no_fields": {
                    "description": "This is another test script",
                    "sequence": [],
                },
                "unexposed_script": {
                    "sequence": [],
                },
            }
        },
    )
    async_expose_entity(hass, "conversation", "script.test_script", True)
    async_expose_entity(hass, "conversation", "script.script_with_no_fields", True)

    entity_registry.async_update_entity(
        "script.test_script", name="script name", aliases={"script alias"}
    )

    area = area_registry.async_create("Living room")
    floor = floor_registry.async_create("2")

    assert llm.ACTION_PARAMETERS_CACHE not in hass.data

    api = await llm.async_get_api(hass, "assist", llm_context)

    tools = [tool for tool in api.tools if isinstance(tool, llm.ScriptTool)]
    assert len(tools) == 2

    tool = tools[0]
    assert tool.name == "test_script"
    assert (
        tool.description
        == "This is a test script. Aliases: ['script name', 'script alias']"
    )
    schema = {
        vol.Required("beer", description="Number of beers"): cv.string,
        vol.Optional("wine"): selector.NumberSelector({"min": 0, "max": 3}),
        vol.Optional("where"): selector.AreaSelector(),
        vol.Optional("area_list"): selector.AreaSelector({"multiple": True}),
        vol.Optional("floor"): selector.FloorSelector(),
        vol.Optional("floor_list"): selector.FloorSelector({"multiple": True}),
        vol.Optional("extra_field"): selector.AreaSelector(),
    }
    assert tool.parameters.schema == schema

    assert hass.data[llm.ACTION_PARAMETERS_CACHE]["script"] == {
        "test_script": (
            "This is a test script. Aliases: ['script name', 'script alias']",
            vol.Schema(schema),
        ),
        "script_with_no_fields": ("This is another test script", vol.Schema({})),
    }

    # Test script with response
    tool_input = llm.ToolInput(
        tool_name="test_script",
        tool_args={
            "beer": "3",
            "wine": 0,
            "where": "Living room",
            "area_list": ["Living room"],
            "floor": "2",
            "floor_list": ["2"],
        },
    )

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        response = await api.async_call_tool(tool_input)

    mock_service_call.assert_awaited_once_with(
        "script",
        "test_script",
        {
            "beer": "3",
            "wine": 0,
            "where": area.id,
            "area_list": [area.id],
            "floor": floor.floor_id,
            "floor_list": [floor.floor_id],
        },
        context=context,
        blocking=True,
        return_response=True,
    )
    assert response == {
        "success": True,
        "result": {"drinks": 2},
    }

    # Test script with no response
    tool_input = llm.ToolInput(
        tool_name="script_with_no_fields",
        tool_args={},
    )

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        side_effect=hass.services.async_call,
    ) as mock_service_call:
        response = await api.async_call_tool(tool_input)

    mock_service_call.assert_awaited_once_with(
        "script",
        "script_with_no_fields",
        {},
        context=context,
        blocking=True,
        return_response=True,
    )
    assert response == {
        "success": True,
        "result": {},
    }

    # Test reload script with new parameters
    config = {
        "script": {
            "test_script": ScriptConfig(
                {
                    "description": "This is a new test script",
                    "sequence": [],
                    "mode": "single",
                    "max": 2,
                    "max_exceeded": "WARNING",
                    "trace": {},
                    "fields": {
                        "beer": {"description": "Number of beers", "required": True},
                    },
                }
            )
        }
    }

    with patch(
        "homeassistant.helpers.entity_component.EntityComponent.async_prepare_reload",
        return_value=config,
    ):
        await hass.services.async_call("script", "reload", blocking=True)

    assert hass.data[llm.ACTION_PARAMETERS_CACHE]["script"] == {}

    api = await llm.async_get_api(hass, "assist", llm_context)

    tools = [tool for tool in api.tools if isinstance(tool, llm.ScriptTool)]
    assert len(tools) == 2

    tool = tools[0]
    assert tool.name == "test_script"
    assert (
        tool.description
        == "This is a new test script. Aliases: ['script name', 'script alias']"
    )
    schema = {vol.Required("beer", description="Number of beers"): cv.string}
    assert tool.parameters.schema == schema

    assert hass.data[llm.ACTION_PARAMETERS_CACHE]["script"] == {
        "test_script": (
            "This is a new test script. Aliases: ['script name', 'script alias']",
            vol.Schema(schema),
        ),
        "script_with_no_fields": ("This is another test script", vol.Schema({})),
    }


async def test_script_tool_name(hass: HomeAssistant) -> None:
    """Test that script tool name is not started with a digit."""
    assert await async_setup_component(hass, "homeassistant", {})
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )

    # Create a script with a unique ID
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "123456": {
                    "description": "This is a test script",
                    "sequence": [],
                    "fields": {
                        "beer": {"description": "Number of beers", "required": True},
                    },
                },
            }
        },
    )
    async_expose_entity(hass, "conversation", "script.123456", True)

    api = await llm.async_get_api(hass, "assist", llm_context)

    tools = [tool for tool in api.tools if isinstance(tool, llm.ScriptTool)]
    assert len(tools) == 1

    tool = tools[0]
    assert tool.name == "_123456"


async def test_selector_serializer(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test serialization of Selectors in Open API format."""
    api = await llm.async_get_api(hass, "assist", llm_context)
    selector_serializer = api.custom_serializer

    assert selector_serializer(selector.ActionSelector()) == {"type": "string"}
    assert selector_serializer(selector.AddonSelector()) == {"type": "string"}
    assert selector_serializer(selector.AreaSelector()) == {"type": "string"}
    assert selector_serializer(selector.AreaSelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.AssistPipelineSelector()) == {"type": "string"}
    assert selector_serializer(
        selector.AttributeSelector({"entity_id": "sensor.test"})
    ) == {"type": "string"}
    assert selector_serializer(selector.BackupLocationSelector()) == {
        "type": "string",
        "pattern": "^(?:\\/backup|\\w+)$",
    }
    assert selector_serializer(selector.BooleanSelector()) == {"type": "boolean"}
    assert selector_serializer(selector.ColorRGBSelector()) == {
        "type": "array",
        "items": {"type": "number"},
        "maxItems": 3,
        "minItems": 3,
        "format": "RGB",
    }
    assert selector_serializer(selector.ColorTempSelector()) == {"type": "number"}
    assert selector_serializer(selector.ColorTempSelector({"min": 0, "max": 1000})) == {
        "type": "number",
        "minimum": 0,
        "maximum": 1000,
    }
    assert selector_serializer(
        selector.ColorTempSelector({"min_mireds": 100, "max_mireds": 1000})
    ) == {"type": "number", "minimum": 100, "maximum": 1000}
    assert selector_serializer(selector.ConditionSelector()) == {
        "type": "array",
        "items": {"nullable": True, "type": "string"},
    }
    assert selector_serializer(selector.ConfigEntrySelector()) == {"type": "string"}
    assert selector_serializer(selector.ConstantSelector({"value": "test"})) == {
        "type": "string",
        "enum": ["test"],
    }
    assert selector_serializer(selector.ConstantSelector({"value": 1})) == {
        "type": "integer",
        "enum": [1],
    }
    assert selector_serializer(selector.ConstantSelector({"value": True})) == {
        "type": "boolean",
        "enum": [True],
    }
    assert selector_serializer(selector.QrCodeSelector({"data": "test"})) == {
        "type": "string"
    }
    assert selector_serializer(selector.ConversationAgentSelector()) == {
        "type": "string"
    }
    assert selector_serializer(selector.CountrySelector()) == {
        "type": "string",
        "format": "ISO 3166-1 alpha-2",
    }
    assert selector_serializer(
        selector.CountrySelector({"countries": ["GB", "FR"]})
    ) == {"type": "string", "enum": ["GB", "FR"]}
    assert selector_serializer(selector.DateSelector()) == {
        "type": "string",
        "format": "date",
    }
    assert selector_serializer(selector.DateTimeSelector()) == {
        "type": "string",
        "format": "date-time",
    }
    assert selector_serializer(selector.DeviceSelector()) == {"type": "string"}
    assert selector_serializer(selector.DeviceSelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.DurationSelector()) == {
        "type": "object",
        "properties": {
            "days": {"type": "number"},
            "hours": {"type": "number"},
            "minutes": {"type": "number"},
            "seconds": {"type": "number"},
            "milliseconds": {"type": "number"},
        },
        "required": [],
    }
    assert selector_serializer(selector.EntitySelector()) == {
        "type": "string",
        "format": "entity_id",
    }
    assert selector_serializer(selector.EntitySelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string", "format": "entity_id"},
    }
    assert selector_serializer(selector.FloorSelector()) == {"type": "string"}
    assert selector_serializer(selector.FloorSelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.IconSelector()) == {"type": "string"}
    assert selector_serializer(selector.LabelSelector()) == {"type": "string"}
    assert selector_serializer(selector.LabelSelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.LanguageSelector()) == {
        "type": "string",
        "format": "RFC 5646",
    }
    assert selector_serializer(
        selector.LanguageSelector({"languages": ["en", "fr"]})
    ) == {"type": "string", "enum": ["en", "fr"]}
    assert selector_serializer(selector.LocationSelector()) == {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "radius": {"type": "number"},
        },
        "required": ["latitude", "longitude"],
    }
    assert selector_serializer(selector.MediaSelector()) == {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string"},
            "media_content_id": {"type": "string"},
            "media_content_type": {"type": "string"},
            "metadata": {"type": "object", "additionalProperties": True},
        },
        "required": ["entity_id", "media_content_id", "media_content_type"],
    }
    assert selector_serializer(selector.NumberSelector({"mode": "box"})) == {
        "type": "number"
    }
    assert selector_serializer(selector.NumberSelector({"min": 30, "max": 100})) == {
        "type": "number",
        "minimum": 30,
        "maximum": 100,
    }
    assert selector_serializer(selector.ObjectSelector()) == {
        "type": "object",
        "additionalProperties": True,
    }
    assert selector_serializer(
        selector.SelectSelector(
            {
                "options": [
                    {"value": "A", "label": "Letter A"},
                    {"value": "B", "label": "Letter B"},
                    {"value": "C", "label": "Letter C"},
                ]
            }
        )
    ) == {"type": "string", "enum": ["A", "B", "C"]}
    assert selector_serializer(
        selector.SelectSelector({"options": ["A", "B", "C"], "multiple": True})
    ) == {
        "type": "array",
        "items": {"type": "string", "enum": ["A", "B", "C"]},
        "uniqueItems": True,
    }
    assert selector_serializer(
        selector.StateSelector({"entity_id": "sensor.test"})
    ) == {"type": "string"}
    target_schema = selector_serializer(selector.TargetSelector())
    target_schema["properties"]["entity_id"]["anyOf"][0][
        "enum"
    ].sort()  # Order is not deterministic
    assert target_schema == {
        "type": "object",
        "properties": {
            "area_id": {
                "anyOf": [
                    {"type": "string", "enum": ["none"]},
                    {"type": "array", "items": {"type": "string", "nullable": True}},
                ]
            },
            "device_id": {
                "anyOf": [
                    {"type": "string", "enum": ["none"]},
                    {"type": "array", "items": {"type": "string", "nullable": True}},
                ]
            },
            "entity_id": {
                "anyOf": [
                    {"type": "string", "enum": ["all", "none"], "format": "lower"},
                    {"type": "string", "nullable": True},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
            "floor_id": {
                "anyOf": [
                    {"type": "string", "enum": ["none"]},
                    {"type": "array", "items": {"type": "string", "nullable": True}},
                ]
            },
            "label_id": {
                "anyOf": [
                    {"type": "string", "enum": ["none"]},
                    {"type": "array", "items": {"type": "string", "nullable": True}},
                ]
            },
        },
        "required": [],
    }

    assert selector_serializer(selector.TemplateSelector()) == {
        "type": "string",
        "format": "jinja2",
    }
    assert selector_serializer(selector.TextSelector()) == {"type": "string"}
    assert selector_serializer(selector.TextSelector({"multiple": True})) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.ThemeSelector()) == {"type": "string"}
    assert selector_serializer(selector.TimeSelector()) == {
        "type": "string",
        "format": "time",
    }
    assert selector_serializer(selector.TriggerSelector()) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert selector_serializer(selector.FileSelector({"accept": ".txt"})) == {
        "type": "string"
    }


async def test_calendar_get_events_tool(hass: HomeAssistant) -> None:
    """Test the calendar get events tool."""
    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set(
        "calendar.test_calendar", "on", {"friendly_name": "Mock Calendar Name"}
    )
    async_expose_entity(hass, "conversation", "calendar.test_calendar", True)
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    tool = next(
        (tool for tool in api.tools if tool.name == "calendar_get_events"), None
    )
    assert tool is not None
    assert tool.parameters.schema["calendar"].container == ["Mock Calendar Name"]

    calls = async_mock_service(
        hass,
        domain=calendar.DOMAIN,
        service=calendar.SERVICE_GET_EVENTS,
        schema=calendar.SERVICE_GET_EVENTS_SCHEMA,
        response={
            "calendar.test_calendar": {
                "events": [
                    {
                        "start": "2025-09-17",
                        "end": "2025-09-18",
                        "summary": "Home Assistant 12th birthday",
                        "description": "",
                    },
                    {
                        "start": "2025-09-17T14:00:00-05:00",
                        "end": "2025-09-18T15:00:00-05:00",
                        "summary": "Champagne",
                        "description": "",
                    },
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )

    tool_input = llm.ToolInput(
        tool_name="calendar_get_events",
        tool_args={
            "calendar": "Mock Calendar Name",
            "range": "today",
        },
    )
    now = dt_util.now()
    with patch("homeassistant.util.dt.now", return_value=now):
        response = await api.async_call_tool(tool_input)

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == calendar.DOMAIN
    assert call.service == calendar.SERVICE_GET_EVENTS
    assert call.data == {
        "entity_id": ["calendar.test_calendar"],
        "start_date_time": now,
        "end_date_time": dt_util.start_of_local_day() + timedelta(days=1),
    }

    assert response == {
        "success": True,
        "result": [
            {
                "start": "2025-09-17",
                "end": "2025-09-18",
                "summary": "Home Assistant 12th birthday",
                "description": "",
                "all_day": True,
            },
            {
                "start": "2025-09-17T14:00:00-05:00",
                "end": "2025-09-18T15:00:00-05:00",
                "summary": "Champagne",
                "description": "",
            },
        ],
    }

    tool_input.tool_args["range"] = "week"
    with patch("homeassistant.util.dt.now", return_value=now):
        response = await api.async_call_tool(tool_input)

    assert len(calls) == 2
    call = calls[1]
    assert call.data == {
        "entity_id": ["calendar.test_calendar"],
        "start_date_time": now,
        "end_date_time": dt_util.start_of_local_day() + timedelta(days=7),
    }


async def test_todo_get_items_tool(hass: HomeAssistant) -> None:
    """Test the todo get items tool."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "todo", {})
    hass.states.async_set(
        "todo.test_list", "0", {"friendly_name": "Mock Todo List Name"}
    )
    async_expose_entity(hass, "conversation", "todo.test_list", True)
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    tool = next((tool for tool in api.tools if tool.name == "todo_get_items"), None)
    assert tool is not None
    assert tool.parameters.schema["todo_list"].container == ["Mock Todo List Name"]

    calls = async_mock_service(
        hass,
        domain=todo.DOMAIN,
        service=todo.TodoServices.GET_ITEMS,
        schema=cv.make_entity_service_schema(todo.TODO_SERVICE_GET_ITEMS_SCHEMA),
        response={
            "todo.test_list": {
                "items": [
                    {
                        "uid": "1234",
                        "summary": "Buy milk",
                        "status": "needs_action",
                    },
                    {
                        "uid": "5678",
                        "summary": "Call mom",
                        "status": "needs_action",
                        "due": "2025-09-17",
                        "description": "Remember birthday",
                    },
                ]
            }
        },
    )

    # Test without status filter (defaults to needs_action)
    result = await tool.async_call(
        hass,
        llm.ToolInput("todo_get_items", {"todo_list": "Mock Todo List Name"}),
        llm_context,
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": ["todo.test_list"],
        "status": ["needs_action"],
    }
    assert result == {
        "success": True,
        "result": [
            {
                "uid": "1234",
                "status": "needs_action",
                "summary": "Buy milk",
            },
            {
                "uid": "5678",
                "status": "needs_action",
                "summary": "Call mom",
                "due": "2025-09-17",
                "description": "Remember birthday",
            },
        ],
    }

    # Test that the status filter is passed correctly to the service call.
    # We don't assert on the response since it is fixed above.
    calls.clear()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            "todo_get_items",
            {"todo_list": "Mock Todo List Name", "status": ["completed"]},
        ),
        llm_context,
    )
    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": ["todo.test_list"],
        "status": ["completed"],
    }


async def test_no_tools_exposed(hass: HomeAssistant) -> None:
    """Test that tools are not exposed when no entities are exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    context = Context()
    llm_context = llm.LLMContext(
        platform="test_platform",
        context=context,
        user_prompt="test_text",
        language="*",
        assistant="conversation",
        device_id=None,
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.tools == []


async def test_merged_api(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test an API instance that merges multiple llm apis."""

    class MyTool(llm.Tool):
        def __init__(self, name: str, description: str) -> None:
            self.name = name
            self.description = description

        async def async_call(
            self, hass: HomeAssistant, tool_input: llm.ToolInput, _: llm.LLMContext
        ) -> JsonObjectType:
            return {"result": {tool_input.tool_name: tool_input.tool_args}}

    api1 = MyAPI(hass=hass, id="api-1", name="API 1")
    api1.prompt = "This is prompt 1"
    api1.tools = [MyTool(name="Tool_1", description="Description 1")]
    llm.async_register_api(hass, api1)

    api2 = MyAPI(hass=hass, id="api-2", name="API 2")
    api2.prompt = "This is prompt 2"
    api2.tools = [MyTool(name="Tool_2", description="Description 2")]
    llm.async_register_api(hass, api2)

    instance = await llm.async_get_api(hass, ["api-1", "api-2"], llm_context)
    assert instance.api.id == "api-1|api-2"

    assert (
        instance.api_prompt
        == """Follow these instructions for tools from "api-1":
This is prompt 1

Follow these instructions for tools from "api-2":
This is prompt 2

"""
    )
    assert [(tool.name, tool.description) for tool in instance.tools] == [
        ("api-1.Tool_1", "Description 1"),
        ("api-2.Tool_2", "Description 2"),
    ]

    # The test tool returns back the provided arguments so we can verify
    # the original tool is invoked with the correct tool name and args.
    result = await instance.async_call_tool(
        llm.ToolInput(tool_name="api-1.Tool_1", tool_args={"arg1": "value1"})
    )
    assert result == {"result": {"Tool_1": {"arg1": "value1"}}}

    result = await instance.async_call_tool(
        llm.ToolInput(tool_name="api-2.Tool_2", tool_args={"arg2": "value2"})
    )
    assert result == {"result": {"Tool_2": {"arg2": "value2"}}}
