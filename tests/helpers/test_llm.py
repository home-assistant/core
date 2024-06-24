"""Tests for the llm helpers."""

from decimal import Decimal
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import async_register_timer_handler
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    intent,
    llm,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml

from tests.common import MockConfigEntry


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


async def test_get_api_no_existing(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting an llm api where no config exists."""
    with pytest.raises(HomeAssistantError):
        await llm.async_get_api(hass, "non-existing", llm_context)


async def test_register_api(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test registering an llm api."""

    class MyAPI(llm.API):
        async def async_get_api_instance(self, _: llm.ToolInput) -> llm.APIInstance:
            """Return a list of tools."""
            return llm.APIInstance(self, "", [], llm_context)

    api = MyAPI(hass=hass, id="test", name="Test")
    llm.async_register_api(hass, api)

    instance = await llm.async_get_api(hass, "test", llm_context)
    assert instance.api is api
    assert api in llm.async_get_apis(hass)

    with pytest.raises(HomeAssistantError):
        llm.async_register_api(hass, api)


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
    assert len(api.tools) == 0

    # Match all
    intent_handler.platforms = None

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert len(api.tools) == 1

    # Match specific domain
    intent_handler.platforms = {"light"}

    api = await llm.async_get_api(hass, "assist", llm_context)
    assert len(api.tools) == 1
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
                }
            }
        },
    )
    async_expose_entity(hass, "conversation", "script.test_script", True)

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
        {"friendly_name": "Kitchen", "temperature": Decimal("0.9")},
    )
    hass.states.async_set(entry2.entity_id, "on", {"friendly_name": "Living Room"})

    def create_entity(device: dr.DeviceEntry, write_state=True) -> None:
        """Create an entity for a device and track entity_id."""
        entity = entity_registry.async_get_or_create(
            "light",
            "test",
            device.id,
            device_id=device.id,
            original_name=str(device.name or "Unnamed Device"),
            suggested_object_id=str(device.name or "unnamed_device"),
        )
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
        )
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

    exposed_entities = llm._get_exposed_entities(hass, llm_context.assistant)
    assert exposed_entities == {
        "light.1": {
            "areas": "Test Area 2",
            "names": "1",
            "state": "unavailable",
        },
        entry1.entity_id: {
            "names": "Kitchen",
            "state": "on",
            "attributes": {
                "temperature": "0.9",
            },
        },
        entry2.entity_id: {
            "areas": "Test Area, Alternative name",
            "names": "Living Room",
            "state": "on",
        },
        "light.test_device": {
            "areas": "Test Area, Alternative name",
            "names": "Test Device",
            "state": "unavailable",
        },
        "light.test_device_2": {
            "areas": "Test Area 2",
            "names": "Test Device 2",
            "state": "unavailable",
        },
        "light.test_device_3": {
            "areas": "Test Area 2",
            "names": "Test Device 3",
            "state": "unavailable",
        },
        "light.test_device_4": {
            "areas": "Test Area 2",
            "names": "Test Device 4",
            "state": "unavailable",
        },
        "light.test_service": {
            "areas": "Test Area, Alternative name",
            "names": "Test Service",
            "state": "unavailable",
        },
        "light.test_service_2": {
            "areas": "Test Area, Alternative name",
            "names": "Test Service",
            "state": "unavailable",
        },
        "light.test_service_3": {
            "areas": "Test Area, Alternative name",
            "names": "Test Service",
            "state": "unavailable",
        },
        "light.unnamed_device": {
            "areas": "Test Area 2",
            "names": "Unnamed Device",
            "state": "unavailable",
        },
        "script.test_script": {
            "description": "This is a test script",
            "names": "test_script",
            "state": "off",
        },
    }
    exposed_entities_prompt = (
        "An overview of the areas and the devices in this smart home:\n"
        + yaml.dump(exposed_entities)
    )
    first_part_prompt = (
        "When controlling Home Assistant always call the intent tools. "
        "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
        "When controlling a device, prefer passing just its name and its domain "
        "(what comes before the dot in its entity id). "
        "When controlling an area, prefer passing just area name and domain."
    )
    no_timer_prompt = "This device does not support timers."

    area_prompt = (
        "When a user asks to turn on all devices of a specific type, "
        "ask user to specify an area, unless there is only one device of that type."
    )
    api = await llm.async_get_api(hass, "assist", llm_context)
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{no_timer_prompt}
{exposed_entities_prompt}"""
    )

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
{exposed_entities_prompt}"""
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
{exposed_entities_prompt}"""
    )

    # Register device for timers
    async_register_timer_handler(hass, device.id, lambda *args: None)

    api = await llm.async_get_api(hass, "assist", llm_context)
    # The no_timer_prompt is gone
    assert api.api_prompt == (
        f"""{first_part_prompt}
{area_prompt}
{exposed_entities_prompt}"""
    )
