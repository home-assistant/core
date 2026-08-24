"""Test the gazetteer fallback in the default agent."""

import pytest

from homeassistant.components import conversation
from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.chat_log import async_get_chat_log
from homeassistant.components.conversation.models import ConversationInput
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    chat_session,
    entity_registry as er,
    intent,
)

from . import expose_entity

from tests.common import async_mock_service

KITCHEN_LIGHT = "light.kitchen_ceiling"
BEDROOM_BLINDS = "cover.bedroom_blinds"


@pytest.fixture
def home(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> ar.AreaEntry:
    """Set up a kitchen with a light and a bedroom with blinds."""
    kitchen = area_registry.async_update(
        area_registry.async_get_or_create("kitchen_id").id, name="Kitchen"
    )
    bedroom = area_registry.async_update(
        area_registry.async_get_or_create("bedroom_id").id, name="Bedroom"
    )

    for entity_id, name, area in (
        (KITCHEN_LIGHT, "Kitchen Ceiling Lights", kitchen),
        (BEDROOM_BLINDS, "Bedroom Blinds", bedroom),
    ):
        domain, object_id = entity_id.split(".")
        entry = entity_registry.async_get_or_create(
            domain, "demo", object_id, suggested_object_id=object_id
        )
        assert entry.entity_id == entity_id
        entity_registry.async_update_entity(
            entity_id, name=name, area_id=area.id, aliases=[er.COMPUTED_NAME]
        )
        hass.states.async_set(
            entity_id, STATE_OFF, attributes={ATTR_FRIENDLY_NAME: name}
        )

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
    """Test a question the corpus phrases two ways is left to hassil.

    "are any lights on" and "how many lights are on" are the same frame, so answering
    it would mean guessing which was asked. hassil's error stands instead.
    """
    result = await conversation.async_converse(
        hass, "are the kichen lights on", None, Context(), None
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
