"""Test the gazetteer fallback in the default agent."""

import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.chat_log import async_get_chat_log
from homeassistant.components.conversation.gazetteer import join_speech
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
    entity_registry as er,
    intent,
)
from homeassistant.setup import async_setup_component

from . import expose_entity

from tests.common import async_mock_service

KITCHEN_LIGHT = "light.kitchen_ceiling"
BEDROOM_BLINDS = "cover.bedroom_blinds"
GARAGE_DOOR = "cover.garage_door"
GARAGE_SHUTTERS = "cover.garage_shutters"


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

    result = await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data["entity_id"] == [KITCHEN_LIGHT]


@pytest.mark.usefixtures("init_components", "home")
async def test_response_uses_display_names(hass: HomeAssistant) -> None:
    """Test the spoken response names the target instead of reading out its id.

    The slots go to the intent handler as registry ids, so the ``HassGetState``
    template would otherwise answer "Cover.bedroom_blinds is off".
    """
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
    """Test a sentence holding two commands runs both of them."""
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
@pytest.mark.parametrize("text", ["asdfgh", "do something"])
async def test_refusal_that_explains_nothing_keeps_the_default_error(
    hass: HomeAssistant, text: str
) -> None:
    """Test noise still gets Home Assistant's own translated error."""
    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code is intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert (
        result.response.speech["plain"]["speech"] == "Sorry, I couldn't understand that"
    )


@pytest.mark.usefixtures("init_components", "home")
async def test_not_used_when_prefer_local_intents(hass: HomeAssistant) -> None:
    """Test the gazetteer does not answer in front of a configured LLM.

    ``async_handle_intents`` is the "prefer local intents" fast path. A sentence it
    declines is one the LLM behind it is meant to get.
    """
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
async def test_follow_up_pronoun_reuses_the_previous_target(
    hass: HomeAssistant,
) -> None:
    """Test "them" refers to what the last successful turn targeted."""
    async_mock_service(hass, "cover", "open_cover")
    close_cover = async_mock_service(hass, "cover", "close_cover")

    result = await conversation.async_converse(
        hass, "open the bedrom blinds", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "close them", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(close_cover) == 1
    assert close_cover[0].data["entity_id"] == BEDROOM_BLINDS


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
async def test_declines_shapes_it_cannot_answer(hass: HomeAssistant) -> None:
    """Test a question whose wording does not say which answer it wants.

    Nothing in "are the kitchen lights on" separates it from "how many kitchen lights
    are on", and the slots are identical, so the frame names no response key and the
    corpus writes several. hassil's error stands rather than a guess.
    """
    result = await conversation.async_converse(
        hass, "are the kichen lights on", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


@pytest.mark.usefixtures("init_components", "home")
@pytest.mark.parametrize(
    ("text", "speech"),
    [
        ("how many kichen lights are on", "0"),
        ("which kichen lights are on", "Not any"),
        ("are any kichen lights on", "No"),
    ],
    ids=["how_many", "which", "any"],
)
async def test_wording_picks_between_identical_frames(
    hass: HomeAssistant, text: str, speech: str
) -> None:
    """Test the frame's own response key answers questions the slots cannot tell apart.

    All three are HassGetState with the same slots. Only the words said separate them,
    which is what the matcher records on the frame.
    """
    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert result.response.speech["plain"]["speech"] == speech


@pytest.mark.usefixtures("init_components", "home")
async def test_pronoun_follows_a_turn_hassil_answered(hass: HomeAssistant) -> None:
    """Test "open it" refers to what the previous hassil turn was about.

    The matcher resolves a pronoun only against targets it is handed, and hassil
    answers most sentences without ever reaching it, so the turn that named the thing
    has to be recorded from there too.
    """
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
async def test_pronoun_follows_the_area_a_turn_named(hass: HomeAssistant) -> None:
    """Test "them" reuses the area a command scoped to, not what it resolved to."""
    async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")

    result = await conversation.async_converse(
        hass, "turn on the kitchen lights", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "turn them off", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(turn_off) == 1
    assert turn_off[0].data["entity_id"] == [KITCHEN_LIGHT]


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
    """Test a pronoun means the turn just given, or none at all.

    "What time is it" succeeds and targets nothing, so it replaces the garage door
    rather than letting "it" reach back past it.
    """
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
@pytest.mark.parametrize(
    ("command", "follow_up", "service"),
    [
        ("close the garage shutters", "open them", "open_cover"),
        ("open the garage shutters", "close them", "close_cover"),
    ],
    ids=["open_them", "close_them"],
)
async def test_them_reopens_the_area_a_cover_command_named(
    hass: HomeAssistant, command: str, follow_up: str, service: str
) -> None:
    """Test "open them" after an area command acts on that area again."""
    async_mock_service(hass, "cover", "open_cover")
    async_mock_service(hass, "cover", "close_cover")
    calls = async_mock_service(hass, "cover", service)

    result = await conversation.async_converse(hass, command, None, Context(), None)
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, follow_up, result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert [call.data["entity_id"] for call in calls] == [GARAGE_SHUTTERS]


@pytest.mark.usefixtures("init_components", "home")
async def test_a_reused_target_still_has_to_suit_the_action(
    hass: HomeAssistant,
) -> None:
    """Test "open them" is refused when the remembered target cannot be opened.

    Reuse does not bypass an action's own constraints: "open" is for covers and
    valves, and the previous turn was about lights.
    """
    async_mock_service(hass, "light", "turn_on")
    calls = async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass, "turn on the kitchen lights", None, Context(), None
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    result = await conversation.async_converse(
        hass, "open them", result.conversation_id, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert not calls


@pytest.mark.usefixtures("home")
async def test_a_custom_sentence_still_leaves_an_antecedent(
    hass: HomeAssistant,
) -> None:
    """Test a phrasing only hassil knows is still something "it" can refer to.

    The matcher validates against the packaged intent catalog, so it can never
    recognize a user's own sentence. Reading the target off the handled intent
    instead of re-running the matcher over the utterance is what keeps this working.
    """
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
    ],
    ids=["two_acknowledgements", "mixed_with_a_query", "already_punctuated", "empties"],
)
def test_join_speech(parts: list[str], expected: str) -> None:
    """Test the frames of one command are spoken as sentences, not one clause.

    "and" would read better for two short acknowledgements, but a coordinated command
    can pair one with a whole sentence, which "and" would run into bad grammar.
    """
    assert join_speech(parts) == expected


@pytest.mark.usefixtures("init_components", "home")
async def test_a_coordinated_command_is_answered_as_sentences(
    hass: HomeAssistant,
) -> None:
    """Test both halves of a coordinated command are spoken, with a stop between."""
    async_mock_service(hass, "light", "turn_off")
    async_mock_service(hass, "cover", "open_cover")

    result = await conversation.async_converse(
        hass,
        "switch off the kichen lights and open the bedrom blinds",
        None,
        Context(),
        None,
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"] == "Turned off the lights. Opening."
    )
