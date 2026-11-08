"""Tests for explicitly authorized Debug console LLM tools."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from http import HTTPStatus
import json
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.auth.models import RefreshToken
from homeassistant.components.debug_console.const import (
    DOMAIN,
    SESSION_TIMEOUT,
    WARNING_VERSION,
)
from homeassistant.components.debug_console.safeguards import (
    DATA_WARNING_ACCEPTANCES,
    async_accept_warning,
)
from homeassistant.components.debug_console.session import (
    DATA_LLM_SESSIONS,
    DATA_MCP_SESSIONS,
)
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import chat_session, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MCPRequestScope

TOOL_NAME = "debug_console__repl"
DOCUMENTATION_URL = "https://www.home-assistant.io/integrations/debug_console"
MCP_API = "/api/mcp"


@pytest.fixture(
    params=[
        pytest.param("mcp_server", id="mcp"),
        pytest.param("ollama", id="local-agent"),
    ]
)
def llm_context(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    request: pytest.FixtureRequest,
    mcp_refresh_token: RefreshToken,
    mcp_request_scope: MCPRequestScope,
) -> Generator[llm.LLMContext]:
    """Return an administrator request from an external or local agent."""
    context = llm.LLMContext(
        platform=request.param,
        context=Context(user_id=hass_admin_user.id),
        language="en",
        assistant="conversation",
        device_id=None,
        agent_id="conversation.test_agent",
    )
    scopes = {
        "mcp_server": mcp_request_scope(mcp_refresh_token),
        "ollama": chat_session.async_get_chat_session(hass, context=context.context),
    }
    with scopes[request.param]:
        yield context


@pytest.fixture
async def setup_llm(hass: HomeAssistant, setup_integration: None) -> None:
    """Load the actual Home Assistant LLM API and Debug console platform."""
    assert await async_setup_component(hass, "llm", {})


@pytest.fixture
async def api(
    hass: HomeAssistant,
    setup_llm: None,
    llm_context: llm.LLMContext,
) -> llm.APIInstance:
    """Return the Home Assistant API after explicit user consent."""
    return await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)


@pytest.mark.usefixtures("setup_llm")
async def test_consent_does_not_require_tool_rediscovery(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """A listed tool works after UI consent without refreshing the API instance."""
    hass.data[DATA_WARNING_ACCEPTANCES].accepted.pop(hass_admin_user.id)
    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)

    assert TOOL_NAME in {tool.name for tool in api.tools}
    tool_input = llm.ToolInput(
        TOOL_NAME,
        {"code": "hass.states.async_set('sensor.console_consent', 'on')\n42"},
    )
    result = await api.async_call_tool(tool_input)

    assert result.error
    assert "Settings > Tools > Debug console" in result.data["error"]
    assert DOCUMENTATION_URL in result.data["error"]
    assert hass.states.get("sensor.console_consent") is None
    assert not hass.data[DATA_MCP_SESSIONS]
    assert not hass.data[DATA_LLM_SESSIONS]

    await async_accept_warning(hass, hass_admin_user.id)
    result = await api.async_call_tool(tool_input)

    assert not result.error
    assert result.data["result"] == {"type": "number", "value": "42"}
    state = hass.states.get("sensor.console_consent")
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("setup_llm")
async def test_existing_warning_acceptance_allows_python(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """A version-one warning acceptance grants agent access without another opt-in."""
    hass.data[DATA_WARNING_ACCEPTANCES].accepted[hass_admin_user.id]["version"] = 1
    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)

    assert TOOL_NAME in {tool.name for tool in api.tools}
    result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "42"}))
    assert not result.error
    assert result.data["result"] == {"type": "number", "value": "42"}


async def test_execute_python(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Execute real Python with top-level await, hass access, and output capture."""
    hass.states.async_set("sensor.console_test", "ready")
    code = (
        "import asyncio\n"
        "await asyncio.sleep(0)\n"
        "print(hass.states.get('sensor.console_test').state)\n"
        "40 + 2"
    )
    with caplog.at_level(logging.WARNING):
        result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": code}))

    assert not result.error
    assert result.data["logs"] == [
        [{"type": "text", "value": "ready", "truncated": False}]
    ]
    assert result.data["result"] == {"type": "number", "value": "42"}
    assert hass_admin_user.id in caplog.text
    assert f"ran code in the debug console via {llm_context.platform}" in caplog.text
    assert code in caplog.text
    tools = [tool for tool in api.tools if tool.integration == DOMAIN]
    assert [tool.name for tool in tools] == [TOOL_NAME]
    assert tools[0].annotations == llm.ToolAnnotations(
        read_only=False, destructive=True, idempotent=False, open_world=True
    )


async def test_execution_error(api: llm.APIInstance) -> None:
    """Report Python failures as tool errors, preserving printed output."""
    result = await api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"code": "print('before')\n1 / 0"})
    )

    assert result.error
    assert "ZeroDivisionError" in result.data["error"]
    assert result.data["logs"] == [
        [{"type": "text", "value": "before", "truncated": False}]
    ]


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
async def test_mcp_server_generates_independent_sessions(
    hass: HomeAssistant, api: llm.APIInstance, llm_context: llm.LLMContext
) -> None:
    """Omitted handles start independent sessions; returned handles resume state."""
    first = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "answer = 41"}))
    second = await api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"code": "'answer' in globals()"})
    )
    assert first.data["session_id"]
    assert second.data["session_id"] != first.data["session_id"]
    assert second.data["result"] == {"type": "boolean", "value": False}

    next_api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    result = await next_api.async_call_tool(
        llm.ToolInput(
            TOOL_NAME, {"code": "answer + 1", "session_id": first.data["session_id"]}
        )
    )
    assert not result.error
    assert result.data["session_id"] == first.data["session_id"]
    assert result.data["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
async def test_mcp_session_handle_returned_on_python_error(
    api: llm.APIInstance,
) -> None:
    """An error leaves its handle and namespace available for the next call."""
    failed = await api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"code": "answer = 41\n1 / 0"})
    )
    assert failed.error
    assert "ZeroDivisionError" in failed.data["error"]
    assert failed.data["session_id"]

    resumed = await api.async_call_tool(
        llm.ToolInput(
            TOOL_NAME, {"code": "answer + 1", "session_id": failed.data["session_id"]}
        )
    )
    assert not resumed.error
    assert resumed.data["session_id"] == failed.data["session_id"]
    assert resumed.data["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
async def test_mcp_reconnect_preserves_credential_session(
    hass: HomeAssistant,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
    mcp_refresh_token: RefreshToken,
    mcp_request_scope: MCPRequestScope,
) -> None:
    """A new authenticated request with the same credential can resume its handle."""
    first = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "answer = 41"}))

    with mcp_request_scope(mcp_refresh_token):
        next_api = await llm.async_get_api(
            hass, llm.LLM_API_HOME_ASSISTANT, llm_context
        )
        result = await next_api.async_call_tool(
            llm.ToolInput(
                TOOL_NAME,
                {"code": "answer + 1", "session_id": first.data["session_id"]},
            )
        )

    assert not result.error
    assert result.data["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
@pytest.mark.parametrize("credential_owner", ["same-user", "other-user"])
async def test_mcp_handle_belongs_to_user_and_credential(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
    mcp_request_scope: MCPRequestScope,
    credential_owner: str,
) -> None:
    """Another credential cannot resume a handle, even for the same administrator."""
    other_user = MockUser(groups=hass_admin_user.groups).add_to_hass(hass)
    await async_accept_warning(hass, other_user.id)
    owner = {"same-user": hass_admin_user, "other-user": other_user}[credential_owner]
    credential = await hass.auth.async_create_refresh_token(
        owner, "https://other.example/"
    )
    first = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret = 42"}))
    other_context = replace(llm_context, context=Context(user_id=owner.id))

    with mcp_request_scope(credential):
        other_api = await llm.async_get_api(
            hass, llm.LLM_API_HOME_ASSISTANT, other_context
        )
        result = await other_api.async_call_tool(
            llm.ToolInput(
                TOOL_NAME,
                {
                    "code": "hass.states.async_set('sensor.unsafe', 'on')",
                    "session_id": first.data["session_id"],
                },
            )
        )

    assert result.error
    assert "Omit session_id" in result.data["error"]
    assert hass.states.get("sensor.unsafe") is None
    assert len(hass.data[DATA_MCP_SESSIONS]) == 1


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
async def test_mcp_unknown_handle_never_creates_session(
    hass: HomeAssistant, api: llm.APIInstance
) -> None:
    """Unknown handles cannot allocate a session or execute Python."""
    result = await api.async_call_tool(
        llm.ToolInput(
            TOOL_NAME,
            {
                "code": "hass.states.async_set('sensor.unsafe', 'on')",
                "session_id": "unknown-session",
            },
        )
    )

    assert result.error
    assert "Omit session_id" in result.data["error"]
    assert not hass.data[DATA_MCP_SESSIONS]
    assert hass.states.get("sensor.unsafe") is None


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
async def test_mcp_expired_handle_never_creates_session(
    hass: HomeAssistant,
    api: llm.APIInstance,
    freezer: FrozenDateTimeFactory,
    mcp_refresh_token: RefreshToken,
    mcp_request_scope: MCPRequestScope,
) -> None:
    """Expired handles fail instead of silently starting a replacement session."""
    first = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret = 42"}))
    freezer.tick(SESSION_TIMEOUT + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    with mcp_request_scope(mcp_refresh_token):
        result = await api.async_call_tool(
            llm.ToolInput(
                TOOL_NAME,
                {
                    "code": "hass.states.async_set('sensor.unsafe', 'on')",
                    "session_id": first.data["session_id"],
                },
            )
        )

    assert result.error
    assert "Omit session_id" in result.data["error"]
    assert not hass.data[DATA_MCP_SESSIONS]
    assert hass.states.get("sensor.unsafe") is None


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
async def test_local_session_survives_new_api_instance(
    hass: HomeAssistant, api: llm.APIInstance, llm_context: llm.LLMContext
) -> None:
    """The conversation automatically retains Python state when its API rebuilds."""
    first = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "answer = 41"}))
    assert not first.error
    assert "session_id" not in first.data
    next_api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)

    result = await next_api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"code": "answer + 1"})
    )
    assert not result.error
    assert result.data["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
async def test_local_conversations_are_isolated(
    hass: HomeAssistant, api: llm.APIInstance, llm_context: llm.LLMContext
) -> None:
    """Separate conversations with the same agent cannot share Python state."""
    await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret = 42"}))

    with chat_session.async_get_chat_session(hass, context=llm_context.context):
        next_api = await llm.async_get_api(
            hass, llm.LLM_API_HOME_ASSISTANT, llm_context
        )
        separate = await next_api.async_call_tool(
            llm.ToolInput(TOOL_NAME, {"code": "'secret' in globals()"})
        )

    assert separate.data["result"] == {"type": "boolean", "value": False}
    original = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret"}))
    assert original.data["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
@pytest.mark.parametrize(
    "context_changes",
    [
        pytest.param({"agent_id": "conversation.other_agent"}, id="other-agent"),
        pytest.param({"platform": "openai_conversation"}, id="other-platform"),
    ],
)
async def test_local_agent_sessions_are_isolated(
    hass: HomeAssistant,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
    context_changes: dict[str, str],
) -> None:
    """Agents and providers remain isolated even within one conversation."""
    await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret = 42"}))
    other_context = replace(llm_context, **context_changes)
    other_api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, other_context)

    result = await other_api.async_call_tool(
        llm.ToolInput(TOOL_NAME, {"code": "'secret' in globals()"})
    )
    assert result.data["result"] == {"type": "boolean", "value": False}


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
async def test_local_missing_conversation_is_rejected(
    hass: HomeAssistant, api: llm.APIInstance
) -> None:
    """Local calls without a conversation cannot fall back to a shared session."""
    token = chat_session.current_session.set(None)
    try:
        result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))
    finally:
        chat_session.current_session.reset(token)

    assert result.error
    assert "active conversation" in result.data["error"]
    assert not hass.data[DATA_LLM_SESSIONS]


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
async def test_local_foreign_conversation_is_rejected(
    hass: HomeAssistant, api: llm.APIInstance
) -> None:
    """A conversation owned by another user cannot provide the Python session."""
    other_user = MockUser().add_to_hass(hass)
    with (
        chat_session.async_get_chat_session(
            hass, context=Context(user_id=other_user.id)
        ),
        pytest.raises(Unauthorized),
    ):
        await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))

    assert not hass.data[DATA_LLM_SESSIONS]


async def test_consent_is_per_user(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
    mcp_request_scope: MCPRequestScope,
) -> None:
    """Another administrator receives neither consent nor session variables."""
    await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "secret = 42"}))
    other_user = MockUser(groups=hass_admin_user.groups).add_to_hass(hass)
    other_context = llm.LLMContext(
        platform=llm_context.platform,
        context=Context(user_id=other_user.id),
        language="en",
        assistant="conversation",
        device_id=None,
        agent_id=llm_context.agent_id,
    )
    other_credential = await hass.auth.async_create_refresh_token(
        other_user, "https://other.example/"
    )
    scopes = {
        "mcp_server": mcp_request_scope(other_credential),
        "ollama": chat_session.async_get_chat_session(
            hass, context=other_context.context
        ),
    }
    with scopes[llm_context.platform]:
        other_api = await llm.async_get_api(
            hass, llm.LLM_API_HOME_ASSISTANT, other_context
        )
        assert TOOL_NAME in {tool.name for tool in other_api.tools}
        result = await other_api.async_call_tool(
            llm.ToolInput(TOOL_NAME, {"code": "'secret' in globals()"})
        )
        assert result.error
        assert DOCUMENTATION_URL in result.data["error"]

        await async_accept_warning(hass, other_user.id)
        result = await other_api.async_call_tool(
            llm.ToolInput(TOOL_NAME, {"code": "'secret' in globals()"})
        )
        assert result.data["result"] == {"type": "boolean", "value": False}


async def test_cached_api_rechecks_consent(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    api: llm.APIInstance,
    llm_context: llm.LLMContext,
) -> None:
    """A cached tool cannot run Python after warning acceptance is removed."""
    hass.data[DATA_WARNING_ACCEPTANCES].accepted.pop(hass_admin_user.id)

    result = await api.async_call_tool(
        llm.ToolInput(
            TOOL_NAME, {"code": "hass.states.async_set('sensor.unsafe', 'on')"}
        )
    )
    assert result.error
    assert "Settings > Tools > Debug console" in result.data["error"]
    assert DOCUMENTATION_URL in result.data["error"]
    assert hass.states.get("sensor.unsafe") is None
    next_api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    assert TOOL_NAME in {tool.name for tool in next_api.tools}


async def test_cached_api_rechecks_warning(
    hass: HomeAssistant, api: llm.APIInstance, llm_context: llm.LLMContext
) -> None:
    """A newer console warning requires renewed UI consent."""
    with patch(
        "homeassistant.components.debug_console.safeguards.WARNING_VERSION",
        WARNING_VERSION + 1,
    ):
        result = await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))
        next_api = await llm.async_get_api(
            hass, llm.LLM_API_HOME_ASSISTANT, llm_context
        )

    assert result.error
    assert "Settings > Tools > Debug console" in result.data["error"]
    assert DOCUMENTATION_URL in result.data["error"]
    assert TOOL_NAME in {tool.name for tool in next_api.tools}


@pytest.mark.parametrize(
    "user_changes",
    [
        pytest.param({"group_ids": []}, id="demoted"),
        pytest.param({"is_active": False}, id="inactive"),
    ],
)
async def test_cached_api_rechecks_admin(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    api: llm.APIInstance,
    user_changes: dict[str, Any],
) -> None:
    """Previously obtained console tools do not retain admin authorization."""
    await hass.auth.async_update_user(hass_admin_user, **user_changes)

    with pytest.raises(Unauthorized):
        await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))


async def test_cached_api_rejects_removed_user(
    hass: HomeAssistant, hass_admin_user: MockUser, api: llm.APIInstance
) -> None:
    """Deleted administrators cannot use a cached tool."""
    await hass.auth.async_remove_user(hass_admin_user)

    with pytest.raises(Unauthorized):
        await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(None, id="missing-context"),
        pytest.param(Context(), id="missing-user"),
    ],
)
async def test_cached_api_requires_user_context(
    api: llm.APIInstance, llm_context: llm.LLMContext, context: Context | None
) -> None:
    """Console execution always requires an authenticated user."""
    llm_context.context = context

    with pytest.raises(Unauthorized):
        await api.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": "1"}))


@pytest.mark.usefixtures("setup_llm")
async def test_assist_does_not_expose_python(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """The device-control API never exposes Python execution."""
    assist_api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, llm_context)

    assert TOOL_NAME not in {tool.name for tool in assist_api.tools}


@pytest.mark.parametrize(
    "args",
    [
        pytest.param({}, id="missing-code"),
        pytest.param({"code": 1}, id="non-string-code"),
        pytest.param({"code": "1", "accept_consent": True}, id="cannot-grant-consent"),
    ],
)
async def test_execution_arguments(api: llm.APIInstance, args: dict[str, Any]) -> None:
    """Validate execution input before running Python."""
    with pytest.raises(probatio.Invalid):
        await api.async_call_tool(llm.ToolInput(TOOL_NAME, args))


@pytest.mark.parametrize(
    "llm_context", [pytest.param("mcp_server", id="mcp")], indirect=True
)
@pytest.mark.parametrize(
    "session_id", [pytest.param("", id="empty"), pytest.param("a" * 65, id="too-long")]
)
async def test_mcp_handle_format(api: llm.APIInstance, session_id: str) -> None:
    """Reject invalid handles before trying to resume a session."""
    with pytest.raises(probatio.Invalid):
        await api.async_call_tool(
            llm.ToolInput(TOOL_NAME, {"code": "1", "session_id": session_id})
        )


@pytest.mark.parametrize(
    "llm_context", [pytest.param("ollama", id="local-agent")], indirect=True
)
async def test_local_schema_has_no_session_parameter(api: llm.APIInstance) -> None:
    """Local agents cannot select or guess their conversation's session identity."""
    with pytest.raises(probatio.Invalid):
        await api.async_call_tool(
            llm.ToolInput(TOOL_NAME, {"code": "1", "session_id": "chosen"})
        )


@pytest.mark.usefixtures("setup_mcp_server")
async def test_mcp_python_requires_ui_consent(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_client: ClientSessionGenerator,
    frontend_ws_client: WebSocketGenerator,
) -> None:
    """A listed tool executes after UI consent without refreshing the MCP list."""
    client = await hass_client()
    response = await client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status == HTTPStatus.OK
    message = await response.json()
    tool = next(
        tool for tool in message["result"]["tools"] if tool["name"] == TOOL_NAME
    )
    assert not tool["annotations"]["readOnlyHint"]
    assert tool["annotations"]["destructiveHint"]
    assert "default" not in tool["inputSchema"]["properties"]["session_id"]

    response = await client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": TOOL_NAME,
                "arguments": {"code": "hass.states.async_set('sensor.unsafe', 'on')"},
            },
        },
    )
    message = await response.json()
    assert message["result"]["isError"]
    error = json.loads(message["result"]["content"][0]["text"])["error"]
    assert "Settings > Tools > Debug console" in error
    assert DOCUMENTATION_URL in error
    assert hass.states.get("sensor.unsafe") is None
    assert not hass.data[DATA_MCP_SESSIONS]

    frontend = await frontend_ws_client(hass_admin_user)
    await frontend.send_json_auto_id({"type": "debug_console/warning/accept"})
    assert (await frontend.receive_json())["success"]
    response = await client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {"code": "answer = 41\nanswer"}},
        },
    )
    message = await response.json()
    assert not message["result"]["isError"]
    result = json.loads(message["result"]["content"][0]["text"])
    assert result["result"] == {"type": "number", "value": "41"}
    assert result["session_id"]

    reconnected_client = await hass_client()
    response = await reconnected_client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": TOOL_NAME,
                "arguments": {"code": "answer + 1", "session_id": result["session_id"]},
            },
        },
    )
    message = await response.json()
    assert not message["result"]["isError"]
    resumed = json.loads(message["result"]["content"][0]["text"])
    assert resumed["session_id"] == result["session_id"]
    assert resumed["result"] == {"type": "number", "value": "42"}


@pytest.mark.parametrize("mcp_read_only", [pytest.param(True, id="read-only")])
@pytest.mark.usefixtures("setup_mcp_server")
async def test_mcp_read_only_hides_python(
    hass_admin_user: MockUser,
    hass_client: ClientSessionGenerator,
    frontend_ws_client: WebSocketGenerator,
) -> None:
    """Read-only MCP configuration excludes arbitrary Python even after consent."""
    client = await hass_client()
    frontend = await frontend_ws_client(hass_admin_user)
    await frontend.send_json_auto_id({"type": "debug_console/warning/accept"})
    assert (await frontend.receive_json())["success"]
    response = await client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    message = await response.json()
    assert TOOL_NAME not in {tool["name"] for tool in message["result"]["tools"]}

    response = await client.post(
        MCP_API,
        headers={"accept": CONTENT_TYPE_JSON},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": TOOL_NAME, "arguments": {"code": "1"}},
        },
    )
    message = await response.json()
    assert message["result"]["isError"]
