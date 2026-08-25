"""Test the gazetteer fallback in the default agent."""

import asyncio
import threading
from typing import Any
from unittest.mock import patch

from gazetteer_matcher import GazetteerMatcher, TargetReference
import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.chat_log import async_get_chat_log
from homeassistant.components.conversation.gazetteer import (
    _PREVIOUS_TARGETS_CAPACITY,
    GazetteerFallback,
    _HomeLock,
    join_speech,
)
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.components.lock import LockState
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
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

from . import expose_entity

from tests.common import MockConfigEntry, async_mock_service

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
async def test_declines_a_frame_it_cannot_answer(hass: HomeAssistant) -> None:
    """Test a frame with no response of its own is left to hassil.

    The matcher leaves the key unset when neither the wording nor the corpus settles
    which of several answers a shape wants. Rather than tie this to whichever shapes
    are unsettled today -- the matcher's vocabulary keeps closing them -- it takes a
    sentence the matcher does answer and removes the key, which is the only thing the
    rule here looks at. Acting mutely is worse than hassil's own error, so nothing is
    said and, importantly, nothing is done.
    """
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
        ("which kichen lights are on", "Not any"),
        ("are any kichen lights on", "No"),
        ("are the kichen lights on", "No"),
    ],
    ids=["how_many", "which", "any", "bare"],
)
async def test_wording_picks_between_identical_frames(
    hass: HomeAssistant, text: str, speech: str
) -> None:
    """Test the frame's own response key answers questions the slots cannot tell apart.

    All four are HassGetState with the same slots. Only the words said separate them,
    which is what the matcher records on the frame -- down to the bare form, which
    names no aggregate at all and is taken to be asking whether any are on.
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
async def test_pronoun_follows_the_area_a_turn_named(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test "them" reuses the area a command scoped to, not what it resolved to.

    A second light in the kitchen is what tells those apart. With only one, an area
    selector and the entity it happened to match turn off the same thing.
    """
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


def test_previous_targets_are_bounded() -> None:
    """Test old conversations are forgotten rather than kept for ever.

    Home Assistant retires a conversation id after its session times out and issues a
    fresh one, so an entry old enough to be evicted is one nothing will ask for again.
    """
    fallback = GazetteerFallback(None)  # type: ignore[arg-type]
    target = TargetReference.for_entity(KITCHEN_LIGHT)

    for index in range(_PREVIOUS_TARGETS_CAPACITY + 1):
        fallback.async_remember(f"conversation-{index}", (target,))

    remembered = list(fallback._previous_targets)
    assert len(remembered) == _PREVIOUS_TARGETS_CAPACITY
    assert "conversation-0" not in remembered
    assert remembered[-1] == f"conversation-{_PREVIOUS_TARGETS_CAPACITY}"


@pytest.mark.usefixtures("init_components", "home")
async def test_an_area_that_vanished_mid_request_is_retried_unplaced(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sentence still gets its chance when the speaker's room went away.

    The home is a snapshot, so an area deleted between building it and interpreting
    makes the matcher reject the context outright. The sentence is still worth trying
    without a room; only the shapes that need one refuse.
    """
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


# The entities gazetteer-matcher's own tests/home.yaml gives these sentences, with the
# same names and aliases, so the cases below are its fixtures run through the agent.
MATCHER_HOME = (
    (
        "light.kitchen_ceiling",
        "Kitchen Ceiling Lights",
        ["ceiling lights"],
        "kitchen_id",
    ),
    ("light.bedroom_lamp", "Bedroom Lamp", ["bedside lamp"], "bedroom_id"),
    ("lock.front_door", "Front Door", ["front door lock"], "hallway_id"),
    (
        "media_player.living_room",
        "Living Room Speakers",
        ["sonos", "stereo", "tv", "television"],
        "living_room_id",
    ),
)


@pytest.fixture
async def matcher_home(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up the part of gazetteer-matcher's test home its fuzzy cases use."""
    assert await async_setup_component(hass, "media_player", {})

    for area_id, name in (
        ("kitchen_id", "Kitchen"),
        ("bedroom_id", "Bedroom"),
        ("hallway_id", "Hallway"),
        ("living_room_id", "Living Room"),
    ):
        area_registry.async_update(
            area_registry.async_get_or_create(area_id).id, name=name
        )

    for entity_id, name, aliases, area_id in MATCHER_HOME:
        domain, object_id = entity_id.split(".")
        # A media player is only pausable while it is playing and says it can.
        state = {
            "lock": LockState.LOCKED,
            "media_player": MediaPlayerState.PLAYING,
        }.get(domain, STATE_OFF)
        attributes: dict[str, Any] = {ATTR_FRIENDLY_NAME: name}
        if domain == "media_player":
            attributes[ATTR_SUPPORTED_FEATURES] = MediaPlayerEntityFeature.PAUSE
        entry = entity_registry.async_get_or_create(
            domain, "demo", object_id, suggested_object_id=object_id
        )
        assert entry.entity_id == entity_id
        entity_registry.async_update_entity(
            entity_id,
            name=name,
            area_id=area_id,
            aliases=[er.COMPUTED_NAME, *aliases],
        )
        hass.states.async_set(entity_id, state, attributes=attributes)
        # Locks are not in DEFAULT_EXPOSED_DOMAINS, and an unexposed entity is not a
        # target for either recognizer.
        expose_entity(hass, entity_id, True)

    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_components", "matcher_home")
@pytest.mark.parametrize(
    ("text", "domain", "service", "entity_id"),
    [
        ("illumanate the bedroom lamp", "light", "turn_on", "light.bedroom_lamp"),
        ("turn on the kitchn lights", "light", "turn_on", "light.kitchen_ceiling"),
        ("turn on the bedrom lamp", "light", "turn_on", "light.bedroom_lamp"),
        (
            "pause televsion",  # codespell:ignore televsion
            "media_player",
            "media_pause",
            "media_player.living_room",
        ),
    ],
    ids=["fuzzy_action", "fuzzy_area", "fuzzy_name", "fuzzy_alias"],
)
async def test_matchers_are_complementary(
    hass: HomeAssistant, text: str, domain: str, service: str, entity_id: str
) -> None:
    """Test sentences hassil cannot answer but the gazetteer can.

    These are gazetteer-matcher's own fuzzy fixtures, which are plausible
    transcription errors: a misheard verb hassil has no template for, and misheard
    area, entity and alias names it cannot resolve. Each one asserts hassil declining
    as well, since a sentence hassil handles never reaches the gazetteer at all.
    """
    calls = async_mock_service(hass, domain, service)
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    user_input = ConversationInput(
        text=text,
        context=Context(),
        conversation_id=None,
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=conversation.HOME_ASSISTANT_AGENT,
    )
    hassil_result = await agent.async_recognize_intent(user_input)
    assert hassil_result is None or hassil_result.unmatched_entities

    result = await conversation.async_converse(hass, text, None, Context(), None)

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    # Some handlers target one entity as a string, others as a list of one.
    assert cv.ensure_list(calls[0].data["entity_id"]) == [entity_id]


@pytest.mark.usefixtures("init_components", "matcher_home")
async def test_a_misheard_name_in_a_question(hass: HomeAssistant) -> None:
    """Test a question about a misheard name, from the matcher's own fixtures."""
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)

    user_input = ConversationInput(
        text="is the frnt door locked",
        context=Context(),
        conversation_id=None,
        device_id=None,
        satellite_id=None,
        language="en",
        agent_id=conversation.HOME_ASSISTANT_AGENT,
    )
    assert await agent.async_recognize_intent(user_input) is None

    result = await conversation.async_converse(
        hass, "is the frnt door locked", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert result.response.speech["plain"]["speech"] == "Yes"


@pytest.mark.usefixtures("init_components", "home")
async def test_the_home_is_built_off_the_event_loop(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test neither building nor refreshing the matcher blocks the event loop.

    Assembling the tagger around a home grows with the size of that home, into
    hundreds of milliseconds for a large one, which is far too long to hold the loop.
    """
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
    real_set_home = GazetteerMatcher.set_home

    def init(self, **kwargs):
        record()
        real_init(self, **kwargs)

    def set_home(self, home):
        record()
        real_set_home(self, home)

    with (
        patch.object(GazetteerMatcher, "__init__", init),
        patch.object(GazetteerMatcher, "set_home", set_home),
    ):
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


async def test_home_lock_lets_interpretations_run_together() -> None:
    """Test the read side does not serialize what it does not need to."""
    lock = _HomeLock()
    both_inside = asyncio.Event()

    async def reader() -> None:
        async with lock.read():
            held.append(1)
            if len(held) == 2:
                both_inside.set()
            await both_inside.wait()

    held: list[int] = []
    async with asyncio.timeout(5):
        await asyncio.gather(reader(), reader())

    assert held == [1, 1]


async def test_home_lock_keeps_a_rebuild_out_while_interpreting() -> None:
    """Test a rebuild waits for the interpretations already in flight."""
    lock = _HomeLock()
    events: list[str] = []
    reading = asyncio.Event()
    release = asyncio.Event()

    async def reader() -> None:
        async with lock.read():
            events.append("read enter")
            reading.set()
            await release.wait()
            events.append("read exit")

    async def writer() -> None:
        await reading.wait()
        async with lock.write():
            events.append("write enter")

    async def finish() -> None:
        await reading.wait()
        # Give the writer every chance to barge in before letting the reader go.
        await asyncio.sleep(0)
        release.set()

    async with asyncio.timeout(5):
        await asyncio.gather(reader(), writer(), finish())

    assert events == ["read enter", "read exit", "write enter"]


async def test_home_lock_holds_off_interpretations_while_rebuilding() -> None:
    """Test an interpretation waits for a rebuild rather than reading a half-swap."""
    lock = _HomeLock()
    events: list[str] = []
    writing = asyncio.Event()
    release = asyncio.Event()

    async def writer() -> None:
        async with lock.write():
            events.append("write enter")
            writing.set()
            await release.wait()
            events.append("write exit")

    async def reader() -> None:
        await writing.wait()
        async with lock.read():
            events.append("read enter")

    async def finish() -> None:
        await writing.wait()
        await asyncio.sleep(0)
        release.set()

    async with asyncio.timeout(5):
        await asyncio.gather(writer(), reader(), finish())

    assert events == ["write enter", "write exit", "read enter"]


@pytest.mark.usefixtures("init_components", "home")
async def test_a_rebuild_waits_for_an_interpretation_in_flight(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test the agent takes the lock, not just that the lock works.

    Both halves run in executor threads, so without the lock a rebuild could swap the
    tagger out from under a sentence being read. Holding one sentence inside the
    matcher is the only way to have something for a rebuild to collide with.
    """
    agent = conversation.async_get_agent(hass)
    assert isinstance(agent, default_agent.DefaultAgent)
    async_mock_service(hass, "light", "turn_on")

    # Build the matcher up front, so the sentences below only read from it.
    await conversation.async_converse(
        hass, "turn on the kichen lights", None, Context(), None
    )

    spans: list[str] = []
    inside = threading.Event()
    release = threading.Event()
    real_interpret = GazetteerMatcher.interpret
    real_set_home = GazetteerMatcher.set_home

    def interpret(self, text, **kwargs):
        """Hold the first sentence inside the matcher until released."""
        spans.append("interpret enter")
        if not inside.is_set():
            inside.set()
            release.wait(timeout=10)
        try:
            return real_interpret(self, text, **kwargs)
        finally:
            spans.append("interpret exit")

    def set_home(self, home):
        spans.append("rebuild enter")
        try:
            real_set_home(self, home)
        finally:
            spans.append("rebuild exit")

    with (
        patch.object(GazetteerMatcher, "interpret", interpret),
        patch.object(GazetteerMatcher, "set_home", set_home),
    ):
        held = hass.async_create_task(
            conversation.async_converse(
                hass, "turn on the kichen lights", None, Context(), None
            )
        )
        await hass.async_add_executor_job(inside.wait, 10)

        # That sentence is now inside the matcher. Outdate the home and ask for
        # another, which cannot be answered without rebuilding first. Nothing here
        # may wait on the held task, which is the point of holding it.
        area_registry.async_update("kitchen_id", name="Scullery")
        assert agent._gazetteer._stale
        waiting = hass.async_create_task(
            conversation.async_converse(
                hass, "turn on the scullary lights", None, Context(), None
            )
        )
        await asyncio.sleep(0.25)

        assert "rebuild enter" not in spans, "rebuilt while a sentence was being read"

        release.set()
        async with asyncio.timeout(10):
            await asyncio.gather(held, waiting)

    assert spans.index("interpret exit") < spans.index("rebuild enter")
    assert spans[-2:] == ["interpret enter", "interpret exit"]
