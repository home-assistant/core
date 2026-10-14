"""Test the gazetteer fallback in the default agent."""

import asyncio
from datetime import timedelta
import threading
import time
from typing import Any
from unittest.mock import patch

from gazetteer_matcher import GazetteerMatcher, TargetReference
import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import default_agent, gazetteer
from homeassistant.components.conversation.chat_log import async_get_chat_log
from homeassistant.components.conversation.gazetteer import (
    GazetteerFallback,
    async_build_home,
    join_speech,
)
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    chat_session,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import expose_entity

from tests.common import MockConfigEntry, async_fire_time_changed, async_mock_service

KITCHEN_LIGHT = "light.kitchen_ceiling"
BEDROOM_BLINDS = "cover.bedroom_blinds"
GARAGE_DOOR = "cover.garage_door"
GARAGE_SHUTTERS = "cover.garage_shutters"


def _outdated(agent: default_agent.DefaultAgent) -> bool:
    """Return whether the gazetteer wants a newer home than it has built."""
    fallback = agent._gazetteer
    return fallback._built_home != fallback._wanted_home


@pytest.fixture
def home(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> ar.AreaEntry:
    """Set up a kitchen with a light, a bedroom with blinds and a garage with covers."""
    kitchen = area_registry.async_update(
        area_registry.async_get_or_create("kitchen_id").id, name="Kitchen"
    )
    bedroom = area_registry.async_update(
        area_registry.async_get_or_create("bedroom_id").id, name="Bedroom"
    )
    garage = area_registry.async_update(
        area_registry.async_get_or_create("garage_id").id, name="Garage"
    )

    # The garage covers carry a device class so an area can be addressed by it
    # ("the garage shutters") without colliding with any one entity's name.
    for entity_id, name, area, state, device_class in (
        (KITCHEN_LIGHT, "Kitchen Ceiling Lights", kitchen, STATE_OFF, None),
        (BEDROOM_BLINDS, "Bedroom Blinds", bedroom, STATE_OFF, None),
        (GARAGE_DOOR, "Garage Door", garage, STATE_CLOSED, "garage"),
        (GARAGE_SHUTTERS, "Side Window", garage, STATE_CLOSED, "shutter"),
    ):
        domain, object_id = entity_id.split(".")
        entry = entity_registry.async_get_or_create(
            domain, "demo", object_id, suggested_object_id=object_id
        )
        assert entry.entity_id == entity_id
        entity_registry.async_update_entity(
            entity_id, name=name, area_id=area.id, aliases=[er.COMPUTED_NAME]
        )
        attributes: dict[str, str] = {ATTR_FRIENDLY_NAME: name}
        if device_class:
            attributes[ATTR_DEVICE_CLASS] = device_class
        hass.states.async_set(entity_id, state, attributes=attributes)

    return kitchen


@pytest.mark.usefixtures("init_components", "home")
async def test_recognizes_a_misheard_name(hass: HomeAssistant) -> None:
    """Test a name hassil cannot resolve is matched by the gazetteer."""
    calls = async_mock_service(hass, "light", "turn_on")
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    user_input = ConversationInput(
        text="turn on the kichen lights",
        context=Context(),
        conversation_id=None,
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=conversation.HOME_ASSISTANT_AGENT,
    )
    hassil_result = await agent.async_recognize_intent(user_input)
    assert hassil_result is None or hassil_result.unmatched_entities

    result = await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [KITCHEN_LIGHT]


@pytest.mark.usefixtures("init_components", "home")
async def test_response_uses_display_names(hass: HomeAssistant) -> None:
    """Test the spoken response names the target instead of reading out its id."""
    result = await conversation.async_converse(
        hass, "what is the state of the bedrom blinds", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.QUERY_ANSWER
    # The template's own `| capitalize` lowercases the rest, as it does for hassil.
    assert result.response.speech["plain"]["speech"] == "Bedroom blinds is off"


@pytest.mark.usefixtures("init_components", "home")
async def test_handles_every_frame_of_a_coordinated_command(
    hass: HomeAssistant,
) -> None:
    """Test a sentence holding two commands runs both, and answers for both."""
    turn_off = async_mock_service(hass, "light", "turn_off")
    open_cover = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass,
        "switch off the kichen lights and open the bedrom blinds",
        None,
        Context(),
        None,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(turn_off) == 1
    assert turn_off[0].data["entity_id"] == [KITCHEN_LIGHT]
    assert len(open_cover) == 1
    assert open_cover[0].data["entity_id"] == BEDROOM_BLINDS
    assert (
        result.response.speech["plain"]["speech"] == "Turned off the lights. Opening."
    )


@pytest.mark.usefixtures("init_components", "home")
async def test_refusal_names_the_target(hass: HomeAssistant) -> None:
    """Test a refusal that resolved a target explains itself."""
    result = await conversation.async_converse(
        hass, "write a poem about my kitchen lights", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code is intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert "Kitchen" in result.response.speech["plain"]["speech"]


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize(
    "text", ["asdfgh", "do something", "asdfgh it", "do something with it"]
)
async def test_refusal_that_explains_nothing_keeps_the_default_error(
    hass: HomeAssistant, text: str
) -> None:
    """Test noise still gets Home Assistant's own translated error.

    A pronoun is tagged wherever it appears, so noise carrying one must not be
    taken for a follow-up the matcher understood.
    """
    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code is intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert (
        result.response.speech["plain"]["speech"] == "Sorry, I couldn't understand that"
    )


@pytest.mark.usefixtures("init_components", "home")
async def test_not_used_when_prefer_local_intents(hass: HomeAssistant) -> None:
    """Test the gazetteer does not answer on the prefer-local-intents path."""
    calls = async_mock_service(hass, "light", "turn_on")
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    user_input = ConversationInput(
        text="turn on the kichen lights",
        context=Context(),
        conversation_id=None,
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=conversation.HOME_ASSISTANT_AGENT,
    )
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, user_input) as chat_log,
    ):
        assert await agent.async_handle_intents(user_input, chat_log) is None

    assert not calls


@pytest.mark.usefixtures("init_components", "home")
async def test_not_used_for_other_languages(hass: HomeAssistant) -> None:
    """Test the matcher's English vocabulary is not applied to other languages."""
    calls = async_mock_service(hass, "light", "turn_on")

    result = await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), "de"
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert not calls


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize("text", ["close them", "close them again", "close it now"])
async def test_follow_up_pronoun_reuses_the_previous_target(
    hass: HomeAssistant, text: str
) -> None:
    """Test a follow-up pronoun refers to what the last successful turn targeted."""
    async_mock_service(hass, "cover", "open_cover")
    close_cover = async_mock_service(hass, "cover", "close_cover")

    result = await conversation.async_converse(
        hass, "open the bedrom blinds", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, text, result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(close_cover) == 1
    assert close_cover[0].data["entity_id"] == BEDROOM_BLINDS


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize("text", ["set it to red", "how hot is it"])
async def test_a_pronoun_the_matcher_leaves_alone_is_not_a_follow_up(
    hass: HomeAssistant, text: str
) -> None:
    """Test "it" the matcher never resolved does not displace hassil's error.

    Only some actions take a follow-up, and "it" is a grammatical subject besides,
    so a tagged pronoun is not on its own a sentence the gazetteer understood.
    """
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    _, interpretation = await agent._gazetteer.async_interpret(text, "test", None)

    assert not interpretation.accepted
    assert not gazetteer.async_refers_back(interpretation)
    assert gazetteer.async_refusal(interpretation) is None


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("turn them back on", "Sorry, I'm not sure what them refers to."),
        ("turn it off again", "Sorry, I'm not sure what it refers to."),
    ],
)
async def test_an_unplaceable_pronoun_explains_itself(
    hass: HomeAssistant, text: str, expected: str
) -> None:
    """Test a follow-up with nothing behind it is answered about the pronoun.

    hassil reads "them back" as the name of a device and reports one nobody named.
    """
    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code is intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert result.response.speech["plain"]["speech"] == expected


@pytest.mark.usefixtures("init_components", "home")
async def test_a_pronoun_refused_over_the_action_names_the_target(
    hass: HomeAssistant,
) -> None:
    """Test an action the antecedent cannot take is refused by naming it."""
    async_mock_service(hass, "light", "turn_on")

    result = await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "open them again", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I can't open the lights in Kitchen; that action doesn't apply."
    )


@pytest.mark.usefixtures("init_components", "home")
async def test_them_reaches_every_target_a_coordinated_command_named(
    hass: HomeAssistant,
) -> None:
    """Test "them" after two commands in one sentence acts on both targets."""
    async_mock_service(hass, "cover", "open_cover")
    close_cover = async_mock_service(hass, "cover", "close_cover")

    result = await conversation.async_converse(
        hass, "open the garage door and side window", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "close them", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert [call.data["entity_id"] for call in close_cover] == [
        GARAGE_DOOR,
        GARAGE_SHUTTERS,
    ]


@pytest.mark.usefixtures("init_components", "home")
async def test_it_is_refused_after_a_coordinated_command(hass: HomeAssistant) -> None:
    """Test "it" names one thing, and two were named, so it picks out nothing."""
    async_mock_service(hass, "cover", "open_cover")
    close_cover = async_mock_service(hass, "cover", "close_cover")

    result = await conversation.async_converse(
        hass, "open the garage door and side window", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "close it", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, it could refer to more than one previous target."
    )
    assert not close_cover


@pytest.mark.usefixtures("init_components", "home")
async def test_them_acts_on_every_target_or_on_none(hass: HomeAssistant) -> None:
    """Test one target the action cannot apply to holds back the rest."""
    async_mock_service(hass, "light", "turn_off")
    open_cover = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass,
        "switch off the kichen lights and open the bedrom blinds",
        None,
        Context(),
        None,
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    open_cover.clear()

    result = await conversation.async_converse(
        hass, "open them", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    # The blinds could have been opened, but half a command is worse than none.
    assert not open_cover


@pytest.mark.usefixtures("init_components", "home")
async def test_home_follows_the_registries(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test a renamed area is resolvable without restarting."""
    calls = async_mock_service(hass, "light", "turn_on")

    area_registry.async_update("kitchen_id", name="Scullery")
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "turn on the scullary lights", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [KITCHEN_LIGHT]


@pytest.mark.usefixtures("init_components", "home")
async def test_hassil_matches_are_left_alone(hass: HomeAssistant) -> None:
    """Test a sentence hassil recognizes never reaches the gazetteer."""
    calls = async_mock_service(hass, "light", "turn_on")
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    agent._gazetteer.async_invalidate()

    result = await conversation.async_converse(
        hass, "turn on the kitchen lights", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    # The matcher was never built, so nothing asked it to interpret anything.
    assert agent._gazetteer._matcher is None


@pytest.mark.usefixtures("init_components", "home")
async def test_unexposed_entities_are_not_targets(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the gazetteer only resolves names exposed to conversation."""
    entry = entity_registry.async_get_or_create("light", "demo", "hidden")
    entity_registry.async_update_entity(
        entry.entity_id, name="Wine Cellar Lamp", aliases=[er.COMPUTED_NAME]
    )
    hass.states.async_set(
        entry.entity_id, STATE_ON, attributes={ATTR_FRIENDLY_NAME: "Wine Cellar Lamp"}
    )
    expose_entity(hass, entry.entity_id, False)
    await hass.async_block_till_done()

    calls = async_mock_service(hass, "light", "turn_off")
    result = await conversation.async_converse(
        hass, "switch off the wine cellar lamp", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert not calls


@pytest.mark.usefixtures("init_components", "home")
async def test_declines_a_frame_it_cannot_answer(hass: HomeAssistant) -> None:
    """Test a frame the matcher cannot answer is left to hassil."""
    calls = async_mock_service(hass, "light", "turn_on")
    real_interpret = GazetteerMatcher.interpret

    def unanswerable(self, text, **kwargs):
        result = real_interpret(self, text, **kwargs)
        for frame in result.frames:
            frame.response_key = None
        return result

    with patch.object(GazetteerMatcher, "interpret", unanswerable):
        result = await conversation.async_converse(
            hass, "turn on the kichen lights", None, Context(), None
        )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert not calls


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize(
    ("text", "speech"),
    [
        ("how many kichen lights are on", "0"),
        ("are the kichen lights on", "No"),
    ],
    ids=["how_many", "any"],
)
async def test_wording_picks_between_identical_frames(
    hass: HomeAssistant, text: str, speech: str
) -> None:
    """Test the frame's own response key tells identical frames apart."""
    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert result.response.speech["plain"]["speech"] == speech


@pytest.mark.usefixtures("init_components", "home")
async def test_pronoun_follows_a_turn_hassil_answered(hass: HomeAssistant) -> None:
    """Test "open it" refers to what the previous hassil turn was about."""
    calls = async_mock_service(hass, "cover", "open_cover")
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    result = await conversation.async_converse(
        hass, "is the garage door closed", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.QUERY_ANSWER
    # Nothing built the matcher, so that turn was hassil's alone.
    assert agent._gazetteer._matcher is None

    result = await conversation.async_converse(
        hass, "open it", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == GARAGE_DOOR


@pytest.mark.usefixtures("init_components", "home")
async def test_pronoun_follows_the_area_a_turn_named(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test "them" reuses the area a command scoped to, not what it resolved to."""
    second = "light.kitchen_lamp"
    entry = entity_registry.async_get_or_create(
        "light", "demo", "kitchen_lamp", suggested_object_id="kitchen_lamp"
    )
    assert entry.entity_id == second
    entity_registry.async_update_entity(
        second, name="Kitchen Lamp", area_id="kitchen_id", aliases=[er.COMPUTED_NAME]
    )
    hass.states.async_set(
        second, STATE_OFF, attributes={ATTR_FRIENDLY_NAME: "Kitchen Lamp"}
    )
    await hass.async_block_till_done()

    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")

    result = await conversation.async_converse(
        hass, "turn on the kitchen lights", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    # What the turn left behind is the selector the sentence used, not its result.
    assert agent._gazetteer._previous_targets[result.conversation_id] == (
        TargetReference.for_area("kitchen_id", domain="light"),
    )

    result = await conversation.async_converse(
        hass, "turn them off", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    # One call per entity, so both lights in the area went off rather than just the
    # one the first sentence resolved to.
    targeted = [
        entity_id
        for call in turn_off
        for entity_id in cv.ensure_list(call.data["entity_id"])
    ]
    assert sorted(targeted) == sorted([KITCHEN_LIGHT, second])


@pytest.mark.usefixtures("init_components", "home")
async def test_a_failed_turn_leaves_the_antecedent_alone(hass: HomeAssistant) -> None:
    """Test a sentence nobody recognized does not strand a following pronoun."""
    calls = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass, "is the garage door closed", None, Context(), None
    )
    conversation_id = result.conversation_id

    result = await conversation.async_converse(
        hass, "asdfgh", conversation_id, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ERROR

    result = await conversation.async_converse(
        hass, "open it", conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1


@pytest.mark.usefixtures("init_components", "home")
async def test_a_turn_with_no_target_clears_the_antecedent(
    hass: HomeAssistant,
) -> None:
    """Test a successful turn that targeted nothing clears the antecedent."""
    calls = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass, "is the garage door closed", None, Context(), None
    )
    conversation_id = result.conversation_id

    result = await conversation.async_converse(
        hass, "what time is it", conversation_id, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "open it", conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert not calls


@pytest.mark.usefixtures("init_components", "home")
async def test_them_reopens_the_area_a_cover_command_named(
    hass: HomeAssistant,
) -> None:
    """Test "open them" after an area command acts on that area again."""
    async_mock_service(hass, "cover", "close_cover")
    calls = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass, "close the garage shutters", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "open them", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert [call.data["entity_id"] for call in calls] == [GARAGE_SHUTTERS]


@pytest.mark.usefixtures("home")
async def test_a_custom_sentence_still_leaves_an_antecedent(
    hass: HomeAssistant,
) -> None:
    """Test a phrasing only hassil knows is still something "it" can refer to."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        conversation.DOMAIN,
        {"conversation": {"intents": {"HassTurnOn": ["give the {name} some juice"]}}},
    )
    assert await async_setup_component(hass, "intent", {})

    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")

    result = await conversation.async_converse(
        hass, "give the kitchen ceiling lights some juice", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "turn it off", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(turn_off) == 1
    assert turn_off[0].data["entity_id"] == [KITCHEN_LIGHT]


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["Unlocking", "Opening"], "Unlocking. Opening."),
        (
            ["Turned off the lights", "Garage door is closed"],
            "Turned off the lights. Garage door is closed.",
        ),
        (
            ["Hello from Home Assistant.", "Opening"],
            "Hello from Home Assistant. Opening.",
        ),
        (["Opening", "", "  "], "Opening."),
        (
            ["Turned off the light", "Turned off the light"],
            "Turned off the light.",
        ),
        (["Turned off the light", "Turned off the light."], "Turned off the light."),
        (
            ["Turned off the light", "Opening", "Turned off the light"],
            "Turned off the light. Opening.",
        ),
    ],
    ids=[
        "two_acknowledgements",
        "mixed_with_a_query",
        "already_punctuated",
        "empties",
        "repeated",
        "repeated_with_punctuation",
        "repeated_apart",
    ],
)
def test_join_speech(parts: list[str], expected: str) -> None:
    """Test the frames of one command are spoken as sentences, not one clause."""
    assert join_speech(parts) == expected


@pytest.mark.usefixtures("init_components", "home")
async def test_an_antecedent_lasts_as_long_as_its_conversation(
    hass: HomeAssistant,
) -> None:
    """Test what a conversation was about is dropped when the conversation ends."""
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    async_mock_service(hass, "light", "turn_on")

    result = await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )
    conversation_id = result.conversation_id
    assert conversation_id in agent._gazetteer._previous_targets

    # Nothing evicts it while other conversations come and go.
    for _ in range(12):
        await conversation.async_converse(
            hass, "turn on the kichen lights", None, Context(), None
        )
    assert conversation_id in agent._gazetteer._previous_targets

    # Its session expiring is what ends it.
    async_fire_time_changed(
        hass, dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT * 2 + timedelta(1)
    )
    await hass.async_block_till_done()

    assert conversation_id not in agent._gazetteer._previous_targets


@pytest.mark.usefixtures("init_components", "home")
async def test_an_area_that_vanished_mid_request_is_retried_unplaced(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sentence is retried unplaced when the speaker's area has gone."""
    calls = async_mock_service(hass, "light", "turn_on")
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "satellite")}
    )
    device_registry.async_update_device(
        device.id, area_id=area_registry.async_get_or_create("ghost_id").id
    )

    real_interpret = GazetteerMatcher.interpret
    placed: list[str | None] = []

    def interpret(self, text, *, context_area=None, **kwargs):
        """Refuse the context once, as the matcher does for an unknown area."""
        placed.append(context_area)
        if context_area is not None:
            raise ValueError(f"unknown context area {context_area!r}")
        return real_interpret(self, text, **kwargs)

    with patch.object(GazetteerMatcher, "interpret", interpret):
        result = await conversation.async_converse(
            hass,
            "turn on the kichen lights",
            None,
            Context(),
            None,
            device_id=device.id,
        )

    assert placed == ["ghost_id", None]
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [KITCHEN_LIGHT]


@pytest.mark.usefixtures("init_components", "home")
async def test_the_home_is_built_off_the_event_loop(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test building the matcher does not block the event loop."""
    off_loop: list[bool] = []

    def record() -> None:
        """Note whether this ran somewhere with a running event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            off_loop.append(True)
        else:
            off_loop.append(False)

    real_init = GazetteerMatcher.__init__

    def init(self, **kwargs):
        record()
        real_init(self, **kwargs)

    with patch.object(GazetteerMatcher, "__init__", init):
        # The first sentence builds the matcher.
        await conversation.async_converse(
            hass, "turn on the kichen lights", None, Context(), None
        )
        assert off_loop == [True]

        # A registry change makes the home stale, so the next one refreshes it.
        area_registry.async_update("kitchen_id", name="Scullery")
        await hass.async_block_till_done()
        await conversation.async_converse(
            hass, "turn on the scullary lights", None, Context(), None
        )

    assert off_loop == [True, True]


@pytest.mark.usefixtures("init_components", "home")
async def test_a_change_during_a_rebuild_is_not_lost(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test a registry change arriving mid-rebuild still outdates the home.

    The home is read before the rebuild is handed to the executor, so a change
    landing during it is not in the snapshot and has to survive the flag reset.
    """
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    async_mock_service(hass, "light", "turn_on")

    await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )

    rebuilding = threading.Event()
    release = threading.Event()
    real_build = gazetteer._build_matcher

    def build(previous, home):
        rebuilding.set()
        release.wait(timeout=5)
        return real_build(previous, home)

    area_registry.async_update("kitchen_id", name="Scullery")
    assert _outdated(agent)

    with patch.object(gazetteer, "_build_matcher", build):
        pending = hass.async_create_task(
            conversation.async_converse(
                hass, "turn on the scullary lights", None, Context(), None
            )
        )
        assert await hass.async_add_executor_job(rebuilding.wait, 5)

        # This arrives after the home was read, so the rebuild in flight misses it.
        area_registry.async_update("bedroom_id", name="Nursery")
        release.set()
        async with asyncio.timeout(5):
            await pending

    assert _outdated(agent), "the change made during the rebuild was counted as built"


async def test_an_antecedent_needs_a_session_to_belong_to(
    hass: HomeAssistant,
) -> None:
    """Test nothing is kept for a turn with no session to end it."""
    fallback = GazetteerFallback(hass)

    fallback.async_remember("orphan", (TargetReference.for_entity(KITCHEN_LIGHT),))

    assert not fallback._previous_targets


@pytest.mark.usefixtures("init_components", "home")
async def test_a_rebuild_that_fails_leaves_the_home_out_of_date(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test a rebuild that did not finish is tried again rather than given up on."""
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    async_mock_service(hass, "light", "turn_on")

    await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )

    area_registry.async_update("kitchen_id", name="Scullery")
    assert _outdated(agent)

    with (
        patch(
            "homeassistant.components.conversation.gazetteer._build_matcher",
            side_effect=RuntimeError("no can do"),
        ),
        pytest.raises(RuntimeError),
    ):
        await conversation.async_converse(
            hass, "turn on the scullary lights", None, Context(), None
        )

    # The matcher still holds the old home, so it has to still count as stale.
    assert _outdated(agent)

    result = await conversation.async_converse(
        hass, "turn on the scullary lights", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize(
    ("registry", "event", "outdated"),
    [
        ("entity", {"action": "update", "changes": {"area_id": None}}, True),
        ("entity", {"action": "update", "changes": {"name": None}}, True),
        ("entity", {"action": "update", "changes": {"icon": None}}, False),
        ("entity", {"action": "remove"}, False),
        ("entity", {"action": "create"}, False),
        ("device", {"action": "update", "changes": {"area_id": None}}, True),
        ("device", {"action": "update", "changes": {"parent_device_id": None}}, True),
        ("device", {"action": "update", "changes": {"sw_version": None}}, False),
        ("device", {"action": "remove"}, False),
    ],
    ids=[
        "entity_moved",
        "entity_renamed",
        "entity_restyled",
        "entity_removed",
        "entity_created",
        "device_moved",
        "device_became_a_child",
        "device_upgraded",
        "device_removed",
    ],
)
async def test_what_outdates_the_home(
    hass: HomeAssistant, registry: str, event: dict[str, Any], outdated: bool
) -> None:
    """Test the registry events that change what an entity is called or where."""
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    matches = {
        "entity": agent._filter_entity_registry_changes,
        "device": agent._filter_device_registry_changes,
    }[registry]

    assert matches(event) is outdated


@pytest.mark.usefixtures("init_components", "home")
async def test_an_entity_with_no_aliases_is_not_a_target(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test an entity nobody has given a name to is not something to act on."""
    entry = entity_registry.async_get_or_create(
        "light", "demo", "nameless", suggested_object_id="nameless"
    )
    entity_registry.async_update_entity(entry.entity_id, aliases=[])
    hass.states.async_set(entry.entity_id, STATE_OFF)
    await hass.async_block_till_done()

    assert entry.entity_id not in async_build_home(hass)["entities"]


@pytest.mark.usefixtures("init_components", "home")
async def test_the_home_is_built_once_for_concurrent_sentences(
    hass: HomeAssistant,
) -> None:
    """Test sentences arriving together do not each build a matcher."""
    async_mock_service(hass, "light", "turn_on")

    builds = 0
    real_build = gazetteer._build_matcher

    def build(previous, home):
        nonlocal builds
        builds += 1
        # Slow enough that the other sentences reach the lock while this holds it.
        time.sleep(0.1)
        return real_build(previous, home)

    with patch.object(gazetteer, "_build_matcher", build):
        await asyncio.gather(
            *(
                conversation.async_converse(
                    hass, "turn on the kichen lights", None, Context(), None
                )
                for _ in range(4)
            )
        )

    assert builds == 1


@pytest.mark.usefixtures("home")
async def test_a_custom_sentence_keeps_its_own_error(hass: HomeAssistant) -> None:
    """Test a sentence somebody wrote themselves is not answered by the gazetteer.

    hassil matched it to the intent it was written for and only the target failed,
    so its error is the answer. The gazetteer would recognize the same words as a
    built-in command and run that instead.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        conversation.DOMAIN,
        {"conversation": {"intents": {"MoodLight": ["please activate {name} now"]}}},
    )
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(
        hass,
        "intent_script",
        {"intent_script": {"MoodLight": {"speech": {"text": "Mood set"}}}},
    )
    calls = async_mock_service(hass, "light", "turn_on")

    result = await conversation.async_converse(
        hass, "please activate kichen lights now", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == "Sorry, I am not aware of any device called kichen lights"
    )
    assert not calls
