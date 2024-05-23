"""Tests for LLM Tools component."""

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.typing import ClientSessionGenerator


async def test_http_api_list(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test LLM API list via HTTP API."""
    assert await async_setup_component(hass, "llm_tools", {})

    client = await hass_client()
    resp = await client.get("/api/llm_tools")

    assert resp.status == 200
    data = await resp.json()

    assert data == ["Assist"]


async def test_http_tool_list(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test LLM Tool list via HTTP API."""
    assert await async_setup_component(hass, "llm_tools", {})

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "OrderBeer"
        description = "Orders beer"

        @property
        def slot_schema(self) -> dict | None:
            """Return a slot schema."""
            return {vol.Required("type"): cv.string}

        async def async_handle(self, intent):
            """Handle the intent."""
            assert intent.context.user_id == hass_admin_user.id
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots["type"]["value"])
            )
            response.async_set_card(
                "Beer ordered", "You chose a {}.".format(intent.slots["type"]["value"])
            )
            return response

    intent.async_register(hass, TestIntentHandler())

    client = await hass_client()
    resp = await client.get("/api/llm_tools/Assist")

    assert resp.status == 200
    data = await resp.json()

    assert data == [
        {
            "description": "Orders beer",
            "name": "OrderBeer",
            "parameters": {
                "properties": {
                    "type": {
                        "type": "string",
                    },
                },
                "required": ["type"],
                "type": "object",
            },
        }
    ]

    resp = await client.get("/api/llm_tools/non-existent")
    assert resp.status == 404

    resp = await client.post(
        "/api/llm_tools/Assist",
        json={"tool_name": "OrderBeer", "tool_args": {"type": "Belgian"}},
    )

    assert resp.status == 200
    data = await resp.json()

    assert data == {
        "card": {
            "simple": {
                "content": "You chose a Belgian.",
                "title": "Beer ordered",
            },
        },
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "language": "en",
        "response_type": "action_done",
        "speech": {
            "plain": {
                "extra_data": None,
                "speech": "I've ordered a Belgian!",
            },
        },
    }

    resp = await client.post(
        "/api/llm_tools/non-existent", json={"tool_name": "OrderBeer"}
    )
    assert resp.status == 404

    resp = await client.post("/api/llm_tools/Assist", json={"tool_name": "OrderBeer"})
    assert resp.status == 500
    data = await resp.json()

    assert data == {
        "error": "MultipleInvalid",
        "error_text": "required key not provided @ data['type']",
    }


async def test_http_tool(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test LLM Tool via HTTP API."""
    assert await async_setup_component(hass, "llm_tools", {})

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "OrderBeer"
        description = "Orders beer"

        @property
        def slot_schema(self) -> dict | None:
            """Return a slot schema."""
            return {vol.Required("type"): cv.string}

        async def async_handle(self, intent):
            """Handle the intent."""
            assert intent.context.user_id == hass_admin_user.id
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots["type"]["value"])
            )
            response.async_set_card(
                "Beer ordered", "You chose a {}.".format(intent.slots["type"]["value"])
            )
            return response

    intent.async_register(hass, TestIntentHandler())

    client = await hass_client()
    resp = await client.get("/api/llm_tools/Assist/OrderBeer")

    assert resp.status == 200
    data = await resp.json()

    assert data == {
        "description": "Orders beer",
        "name": "OrderBeer",
        "parameters": {
            "properties": {
                "type": {
                    "type": "string",
                },
            },
            "required": ["type"],
            "type": "object",
        },
    }

    resp = await client.get("/api/llm_tools/non-existent/non-existent")
    assert resp.status == 404

    resp = await client.get("/api/llm_tools/Assist/non-existent")
    assert resp.status == 404

    resp = await client.post("/api/llm_tools/Assist/OrderBeer", json={"type": "Lager"})

    assert resp.status == 200
    data = await resp.json()

    assert data == {
        "card": {
            "simple": {
                "content": "You chose a Lager.",
                "title": "Beer ordered",
            },
        },
        "data": {
            "failed": [],
            "success": [],
            "targets": [],
        },
        "language": "en",
        "response_type": "action_done",
        "speech": {
            "plain": {
                "extra_data": None,
                "speech": "I've ordered a Lager!",
            },
        },
    }

    resp = await client.post("/api/llm_tools/non-existent/non-existent")
    assert resp.status == 404

    resp = await client.post("/api/llm_tools/Assist/non-existent")
    assert resp.status == 404

    resp = await client.post("/api/llm_tools/Assist/OrderBeer")

    assert resp.status == 500
    data = await resp.json()

    assert data == {
        "error": "MultipleInvalid",
        "error_text": "required key not provided @ data['type']",
    }
