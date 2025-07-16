"""Tests for the OpenRouter integration."""

from unittest.mock import AsyncMock

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401


@pytest.fixture(autouse=True)
def freeze_the_time():
    """Freeze the time."""
    with freeze_time("2024-05-24 12:00:00", tz_offset=0):
        yield


@pytest.mark.parametrize("enable_assist", [True, False], ids=["assist", "no_assist"])
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_default_prompt(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test that the default prompt works."""
    await setup_integration(hass, mock_config_entry)
    result = await conversation.async_converse(
        hass,
        "hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.gpt_3_5_turbo",
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_chat_log.content[1:] == snapshot
    call = mock_openai_client.chat.completions.create.call_args_list[0][1]
    assert call["model"] == "gpt-3.5-turbo"
    assert call["extra_headers"] == {
        "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        "X-Title": "Home Assistant",
    }
