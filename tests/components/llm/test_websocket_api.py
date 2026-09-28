"""Tests for the LLM integration websocket API."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


class _StubAPI(llm.API):
    """Minimal LLM API used to populate the registry."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self, api_prompt="", llm_context=llm_context, tools=[]
        )


@pytest.fixture(autouse=True)
async def setup_llm(hass: HomeAssistant) -> None:
    """Set up the LLM integration."""
    assert await async_setup_component(hass, "llm", {})


@pytest.mark.parametrize(
    ("registered_apis", "expected_apis"),
    [
        pytest.param([], [{"id": "assist", "name": "Assist"}], id="assist_only"),
        pytest.param(
            [("test-api", "Test API")],
            [
                {"id": "assist", "name": "Assist"},
                {"id": "test-api", "name": "Test API"},
            ],
            id="registered_api",
        ),
    ],
)
async def test_list_apis(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    registered_apis: list[tuple[str, str]],
    expected_apis: list[dict[str, str]],
) -> None:
    """Test listing the registered LLM APIs."""
    for api_id, name in registered_apis:
        llm.async_register_api(hass, _StubAPI(hass=hass, id=api_id, name=name))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "llm/api/list"})
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"apis": expected_apis}


async def test_list_apis_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test listing the LLM APIs is only allowed for admins."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json_auto_id({"type": "llm/api/list"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
