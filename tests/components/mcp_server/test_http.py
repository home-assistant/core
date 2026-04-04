"""Test the Model Context Protocol Server init module."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from http import HTTPStatus
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import mcp
import mcp.client.session
import mcp.client.sse
import mcp.client.streamable_http
from mcp.shared.exceptions import McpError
import pytest

from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.mcp_server.const import STATELESS_LLM_API
from homeassistant.components.mcp_server.http import (
    MESSAGES_API,
    SSE_API,
    STREAMABLE_API,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LLM_HASS_API, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    llm,
)
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import MockConfigEntry, setup_test_component_platform
from tests.components.light.common import MockLight
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)

TEST_ENTITY = "light.kitchen"
EXPOSED_ENTITIES_RESOURCE_URI = "homeassistant://assist/exposed-entities"


class MockLLMAPI(llm.API):
    """Test LLM API."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return a test API instance."""
        return llm.APIInstance(
            api=self,
            api_prompt="Test prompt",
            llm_context=llm_context,
            tools=[],
        )


@pytest.fixture(name="llm_hass_api")
def llm_hass_api_fixture(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> str | list[str]:
    """Fixture for the config entry llm_hass_api."""
    llm_hass_api: str | list[str] = getattr(request, "param", [llm.LLM_API_ASSIST])

    if isinstance(llm_hass_api, str):
        llm_api_ids = [llm_hass_api]
    else:
        llm_api_ids = llm_hass_api

    if "test-api" in llm_api_ids:
        llm.async_register_api(
            hass, MockLLMAPI(hass=hass, id="test-api", name="Test API")
        )

    return llm_hass_api


INITIALIZE_MESSAGE = {
    "jsonrpc": "2.0",
    "id": "request-id-1",
    "method": "initialize",
    "params": {
        "protocolVersion": "1.0",
        "capabilities": {},
        "clientInfo": {
            "name": "test",
            "version": "1",
        },
    },
}
EVENT_PREFIX = "event: "
DATA_PREFIX = "data: "
EXPECTED_PROMPT_SUFFIX = """
- names: Kitchen Light
  domain: light
  areas: Kitchen
"""


@pytest.fixture
async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.fixture(autouse=True)
async def mock_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    setup_integration: None,
) -> None:
    """Fixture to expose entities to the conversation agent."""
    entity = MockLight("Kitchen Light", STATE_OFF)
    entity.entity_id = TEST_ENTITY
    entity.unique_id = "test-light-unique-id"
    setup_test_component_platform(hass, LIGHT_DOMAIN, [entity])

    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()
    kitchen = area_registry.async_get_or_create("Kitchen")
    entity_registry.async_update_entity(TEST_ENTITY, area_id=kitchen.id)

    async_expose_entity(hass, CONVERSATION_DOMAIN, TEST_ENTITY, True)


async def sse_response_reader(
    response: aiohttp.ClientResponse,
) -> AsyncGenerator[tuple[str, str]]:
    """Read SSE responses from the server and emit event messages.

    SSE responses are formatted as:
        event: event-name
        data: event-data
    and this function emits each event-name and event-data as a tuple.
    """
    it = aiter(response.content)
    while True:
        line = (await anext(it)).decode()
        if not line.startswith(EVENT_PREFIX):
            raise ValueError("Expected event")
        event = line[len(EVENT_PREFIX) :].strip()
        line = (await anext(it)).decode()
        if not line.startswith(DATA_PREFIX):
            raise ValueError("Expected data")
        data = line[len(DATA_PREFIX) :].strip()
        line = (await anext(it)).decode()
        assert line == "\r\n"
        yield event, data


async def test_http_sse(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test SSE endpoint can be used to receive MCP messages."""

    client = await hass_client()

    # Start an SSE session
    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.OK

    # Decode a single SSE response that sends the messages endpoint
    reader = sse_response_reader(response)
    event, endpoint_url = await anext(reader)
    assert event == "endpoint"

    # Send an initialize message on the messages endpoint
    response = await client.post(endpoint_url, json=INITIALIZE_MESSAGE)
    assert response.status == HTTPStatus.OK

    # Decode the initialize response event message from the SSE stream
    event, data = await anext(reader)
    assert event == "message"
    message = json.loads(data)
    assert message.get("jsonrpc") == "2.0"
    assert message.get("id") == "request-id-1"
    assert "serverInfo" in message.get("result", {})
    assert "protocolVersion" in message.get("result", {})


async def test_http_messages_missing_session_id(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the tools list endpoint."""

    client = await hass_client()
    response = await client.post(MESSAGES_API.format(session_id="invalid-session-id"))
    assert response.status == HTTPStatus.NOT_FOUND
    response_data = await response.text()
    assert response_data == "Could not find session ID 'invalid-session-id'"


async def test_http_messages_invalid_message_format(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the tools list endpoint."""

    client = await hass_client()
    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.OK
    reader = sse_response_reader(response)
    event, endpoint_url = await anext(reader)
    assert event == "endpoint"

    response = await client.post(endpoint_url, json={"invalid": "message"})
    assert response.status == HTTPStatus.BAD_REQUEST
    response_data = await response.text()
    assert response_data == "Could not parse message"


async def test_http_sse_multiple_config_entries(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the SSE endpoint will fail with multiple config entries.

    This cannot happen in practice as the integration only supports a single
    config entry, but this is added for test coverage.
    """

    config_entry = MockConfigEntry(
        domain="mcp_server", data={CONF_LLM_HASS_API: ["llm-api-id"]}
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_client()

    # Attempt to start an SSE session will fail
    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.NOT_FOUND
    response_data = await response.text()
    assert "Found multiple Model Context Protocol" in response_data


async def test_http_sse_no_config_entry(
    hass: HomeAssistant,
    setup_integration: None,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the SSE endpoint fails with a missing config entry."""

    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    client = await hass_client()

    # Start an SSE session
    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.NOT_FOUND
    response_data = await response.text()
    assert "Model Context Protocol server is not configured" in response_data


async def test_http_messages_no_config_entry(
    hass: HomeAssistant,
    setup_integration: None,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the message endpoint will fail if the config entry is unloaded."""

    client = await hass_client()

    # Start an SSE session
    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.OK
    reader = sse_response_reader(response)
    event, endpoint_url = await anext(reader)
    assert event == "endpoint"

    # Invalidate the session by unloading the config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    # Reload the config entry and ensure the session is not found
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    response = await client.post(endpoint_url, json=INITIALIZE_MESSAGE)
    assert response.status == HTTPStatus.NOT_FOUND
    response_data = await response.text()
    assert "Could not find session ID" in response_data


async def test_http_requires_authentication(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test the SSE endpoint requires authentication."""

    client = await hass_client_no_auth()

    response = await client.get(SSE_API)
    assert response.status == HTTPStatus.UNAUTHORIZED

    response = await client.post(MESSAGES_API.format(session_id="session-id"))
    assert response.status == HTTPStatus.UNAUTHORIZED


@pytest.fixture(params=["sse", "streamable"])
def mcp_protocol(request: pytest.FixtureRequest):
    """Fixture to parametrize tests with different MCP protocols."""
    return request.param


@pytest.fixture
async def mcp_url(mcp_protocol: str, hass_client: ClientSessionGenerator) -> str:
    """Fixture to get the MCP integration URL."""
    if mcp_protocol == "sse":
        url = SSE_API
    else:
        url = STREAMABLE_API
    client = await hass_client()
    return str(client.make_url(url))


@asynccontextmanager
async def mcp_sse_session(
    hass: HomeAssistant,
    mcp_url: str,
    hass_supervisor_access_token: str,
) -> AsyncGenerator[mcp.client.session.ClientSession]:
    """Create an MCP session."""

    headers = {"Authorization": f"Bearer {hass_supervisor_access_token}"}

    async with (
        mcp.client.sse.sse_client(mcp_url, headers=headers) as streams,
        mcp.client.session.ClientSession(*streams) as session,
    ):
        await session.initialize()
        yield session


@asynccontextmanager
async def mcp_streamable_session(
    hass: HomeAssistant,
    mcp_url: str,
    hass_supervisor_access_token: str,
) -> AsyncGenerator[mcp.client.session.ClientSession]:
    """Create an MCP session."""

    headers = {"Authorization": f"Bearer {hass_supervisor_access_token}"}

    async with (
        mcp.client.streamable_http.streamable_http_client(
            mcp_url, http_client=create_async_httpx_client(hass, headers=headers)
        ) as (read_stream, write_stream, _),
        mcp.client.session.ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        yield session


@pytest.fixture(name="mcp_client")
def mcp_client_fixture(mcp_protocol: str) -> Any:
    """Fixture to parametrize tests with different MCP clients."""
    if mcp_protocol == "sse":
        return mcp_sse_session
    if mcp_protocol == "streamable":
        return mcp_streamable_session
    raise ValueError(f"Unknown MCP protocol: {mcp_protocol}")


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_tools_list(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the tools list endpoint."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.list_tools()

    # Pick a single arbitrary tool and test that description and parameters
    # are converted correctly.
    tool = next(iter(tool for tool in result.tools if tool.name == "HassTurnOn"))
    assert tool.name == "HassTurnOn"
    assert tool.description is not None
    assert tool.inputSchema
    assert tool.inputSchema.get("type") == "object"
    properties = tool.inputSchema.get("properties")
    assert properties.get("name") == {"type": "string"}


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_tool_call(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the tool call endpoint."""

    state = hass.states.get("light.kitchen")
    assert state
    assert state.state == STATE_OFF

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.call_tool(
            name="HassTurnOn",
            arguments={"name": "kitchen light"},
        )

    assert not result.isError
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    # The content is the raw tool call payload
    content = json.loads(result.content[0].text)
    assert content.get("data", {}).get("success")
    assert not content.get("data", {}).get("failed")

    # Verify tool call invocation
    state = hass.states.get("light.kitchen")
    assert state
    assert state.state == STATE_ON


async def test_mcp_tool_call_failed(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the tool call endpoint with a failure."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.call_tool(
            name="HassTurnOn",
            arguments={"name": "backyard"},
        )

    assert result.isError
    assert len(result.content) == 1
    assert result.content[0].type == "text"
    assert "Error calling tool" in result.content[0].text


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_prompt_list(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the list prompt endpoint."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.list_prompts()

    assert len(result.prompts) == 1
    prompt = result.prompts[0]
    assert prompt.name == "Assist"
    assert prompt.description == "Default prompt for Home Assistant Assist API"


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_prompt_get(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the get prompt endpoint."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.get_prompt(name="Assist")

    assert result.description == "Default prompt for Home Assistant Assist API"
    assert len(result.messages) == 1
    assert result.messages[0].role == "assistant"
    assert result.messages[0].content.type == "text"
    assert "When controlling Home Assistant" in result.messages[0].content.text
    assert result.messages[0].content.text.endswith(EXPECTED_PROMPT_SUFFIX)


async def test_get_unknown_prompt(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the get prompt endpoint."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        with pytest.raises(McpError):
            await session.get_prompt(name="Unknown")


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_resources_list(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the resource list endpoint."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.list_resources()

    assert len(result.resources) == 1
    resource = result.resources[0]
    assert str(resource.uri) == EXPOSED_ENTITIES_RESOURCE_URI
    assert resource.name == "assist_exposed_entities"
    assert resource.title == "Assist exposed entities"
    assert resource.description is not None
    assert resource.mimeType == "text/yaml"


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_resource_read(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test reading an MCP resource."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        resources = await session.list_resources()
        resource = resources.resources[0]
        result = await session.read_resource(resource.uri)

    assert len(result.contents) == 1
    content = result.contents[0]
    assert content.uri == resource.uri
    assert content.mimeType == "text/yaml"
    parsed = parse_yaml(content.text)
    assert parsed["assistant"] == "conversation"
    assert parsed["entities"] == [
        {
            "entity_id": "light.kitchen",
            "names": "Kitchen Light",
            "domain": "light",
            "state": "off",
            "areas": "Kitchen",
        }
    ]


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_resource_read_includes_attributes_and_local_timestamps(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test resource payload reuses the Assist exposed entity context."""

    await hass.config.async_set_time_zone("America/New_York")
    hass.states.async_set(
        "climate.hallway",
        "heat",
        {
            "friendly_name": "Hallway Thermostat",
            "current_temperature": 21,
            "temperature": 22,
        },
    )
    async_expose_entity(hass, CONVERSATION_DOMAIN, "climate.hallway", True)

    hass.states.async_set(
        "sensor.next_alarm",
        "2024-01-15T10:30:00+00:00",
        {
            "device_class": "timestamp",
            "friendly_name": "Next Alarm",
        },
    )
    async_expose_entity(hass, CONVERSATION_DOMAIN, "sensor.next_alarm", True)

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        resources = await session.list_resources()
        resource = resources.resources[0]
        result = await session.read_resource(resource.uri)

    parsed = parse_yaml(result.contents[0].text)
    entities = {entity["entity_id"]: entity for entity in parsed["entities"]}

    assert entities["climate.hallway"]["attributes"] == {
        "current_temperature": "21",
        "temperature": "22",
    }
    assert entities["sensor.next_alarm"]["state"] == "2024-01-15T05:30:00-05:00"
    assert entities["sensor.next_alarm"]["attributes"] == {
        "device_class": "timestamp",
    }


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_resource_read_includes_scripts_and_calendars(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test resource payload includes all exposed Assist objects."""

    hass.states.async_set(
        "calendar.household", "on", {"friendly_name": "Household Calendar"}
    )
    async_expose_entity(hass, CONVERSATION_DOMAIN, "calendar.household", True)

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "bedtime": {
                    "alias": "Bedtime",
                    "description": "Prepare the house for bed",
                    "sequence": [],
                }
            }
        },
    )
    async_expose_entity(hass, CONVERSATION_DOMAIN, "script.bedtime", True)
    await hass.async_block_till_done()

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        resources = await session.list_resources()
        resource = resources.resources[0]
        result = await session.read_resource(resource.uri)

    entities = {
        entity["entity_id"]: entity
        for entity in parse_yaml(result.contents[0].text)["entities"]
    }
    assert entities["calendar.household"]["domain"] == "calendar"
    assert entities["calendar.household"]["names"] == "Household Calendar"
    assert entities["script.bedtime"]["domain"] == "script"
    assert entities["script.bedtime"]["names"] == "Bedtime"


@pytest.mark.parametrize(
    ("llm_hass_api", "expected_count"),
    [
        ("test-api", 0),
        ([llm.LLM_API_ASSIST, "test-api"], 1),
    ],
)
async def test_mcp_resources_respect_selected_llm_api(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
    expected_count: int,
) -> None:
    """Test resources are only exposed when Assist is selected."""

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        result = await session.list_resources()

    assert len(result.resources) == expected_count


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST, STATELESS_LLM_API])
async def test_mcp_resource_read_unknown_resource(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test reading an unknown MCP resource."""

    unknown_uri = mcp.types.Resource(
        uri="homeassistant://assist/missing",
        name="missing",
    ).uri

    async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
        with pytest.raises(McpError, match="Unknown resource"):
            await session.read_resource(unknown_uri)


@pytest.mark.parametrize("llm_hass_api", [llm.LLM_API_ASSIST])
async def test_mcp_tool_call_unicode(
    hass: HomeAssistant,
    setup_integration: None,
    mcp_url: str,
    mcp_client: Any,
    hass_supervisor_access_token: str,
) -> None:
    """Test the tool call endpoint preserves unicode characters."""

    # Mock the API instance
    mock_api = AsyncMock()
    mock_api.api.name = "Assist"
    mock_api.tools = []
    mock_api.custom_serializer = None
    mock_api.async_call_tool.return_value = {"message": "这是一个测试"}

    # We need to ensure when the server calls llm.async_get_api, it gets our mock
    # async_get_api is awaited, so we need an AsyncMock
    with patch(
        "homeassistant.helpers.llm.async_get_api", new_callable=AsyncMock
    ) as mock_get_api:
        mock_get_api.return_value = mock_api
        async with mcp_client(hass, mcp_url, hass_supervisor_access_token) as session:
            result = await session.call_tool(
                name="AnyTool",
                arguments={},
            )

    assert not result.isError
    assert len(result.content) == 1
    assert result.content[0].type == "text"

    # Check that the text contains the raw unicode characters, NOT the escaped version
    response_text = result.content[0].text
    assert "这是一个测试" in response_text
    assert "\\u" not in response_text
