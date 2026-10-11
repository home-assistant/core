"""Integration tests for the Mistral AI config entry setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from httpx import ConnectError, Request, Response
from mistralai.client import errors
import pytest

from homeassistant.components.mistral_ai import DOMAIN
from homeassistant.components.mistral_ai.const import (
    DEFAULT_CONVERSATION_NAME,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def _response(status_code: int) -> Response:
    """Build a response with the given status code."""
    return Response(
        status_code, request=Request("GET", "https://api.mistral.ai/v1/models")
    )


class _FakeModels:
    def __init__(self, list_error: Exception | None = None) -> None:
        self.list_async = AsyncMock(
            return_value=SimpleNamespace(data=[]), side_effect=list_error
        )


class _FakeMistral:
    def __init__(
        self, api_key=None, async_client=None, list_error: Exception | None = None
    ) -> None:
        self.models = _FakeModels(list_error)
        self.chat = None
        self.audio = None

    def __getattr__(self, name):
        # Lazy sub-SDK access used by create_client preload.
        if name in ("chat", "models", "audio"):
            return self.models
        raise AttributeError(name)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mistral",
        data={"api_key": "test-key"},
        version=2,
        subentries_data=[
            {
                "subentry_type": "conversation",
                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                "title": DEFAULT_CONVERSATION_NAME,
                "unique_id": None,
            },
        ],
    )


async def test_config_entry_creates_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Setting up the entry creates a conversation entity."""
    entry = _entry()
    entry.add_to_hass(hass)

    # The conversation dependency needs the "homeassistant" component loaded
    # (it initializes the ExposedEntities registry).
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.mistral_ai.async_create_client",
            new_callable=AsyncMock,
            return_value=_FakeMistral(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all()
    entity_ids = {state.entity_id for state in states}
    domains = {entity_id.split(".")[0] for entity_id in entity_ids}
    assert "conversation" in domains

    # Exactly one conversation entity from this integration.
    mistral_entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.platform == DOMAIN
    ]
    assert len(mistral_entities) == 1


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (ConnectError("boom"), ConfigEntryState.SETUP_RETRY),
        (errors.NoResponseError(), ConfigEntryState.SETUP_RETRY),
        (errors.SDKError("server error", _response(500)), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_error_retries(
    hass: HomeAssistant, error: Exception, expected_state: ConfigEntryState
) -> None:
    """Expected Mistral/network failures put the entry in retry state."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mistral_ai.async_create_client",
        new_callable=AsyncMock,
        return_value=_FakeMistral(list_error=error),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state


async def test_setup_auth_error_starts_reauth(hass: HomeAssistant) -> None:
    """A 401 during setup triggers the reauthentication flow."""
    entry = _entry()
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mistral_ai.async_create_client",
        new_callable=AsyncMock,
        return_value=_FakeMistral(
            list_error=errors.SDKError("unauthorized", _response(401))
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, include_uninitialized=True
    )
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
