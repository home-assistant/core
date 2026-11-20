"""Tests for code mode."""

import asyncio
from datetime import timedelta
from typing import Any, override
from unittest.mock import patch

import probatio
import psutil
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.llm import code_mode as code_mode_api
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, config_validation as cv, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


class GetStateTool(llm.Tool):
    """Tool that returns a fake state."""

    name = "test__get-state"
    title = "Read a light"
    description = "Get the state\nof an entity"
    parameters = probatio.Schema(
        {
            probatio.Required("entity_id", description="The entity"): cv.string,
            probatio.Optional("attributes"): [probatio.In(["brightness", "color"])],
            probatio.Optional("retries"): probatio.Any(int, None),
        }
    )
    integration = "test"

    def __init__(self) -> None:
        """Init the class."""
        self.calls: list[str] = []
        self.llm_contexts: list[llm.LLMContext] = []

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Return a fake state."""
        entity_id = tool_input.tool_args["entity_id"]
        if entity_id == "light.broken":
            raise HomeAssistantError("Light is broken")
        if entity_id == "light.failed":
            return llm.ToolResult(data={"reason": "No power"}, error=True)
        if entity_id == "light.slow":
            await asyncio.sleep(10)
        self.calls.append(entity_id)
        self.llm_contexts.append(llm_context)
        state = "on" if entity_id.endswith(("0", "5")) else "off"
        return llm.ToolResult(data={"entity_id": entity_id, "state": state})


class TestAPI(llm.API):
    """API with a test tool."""

    __test__ = False

    def __init__(self, hass: HomeAssistant, tool: llm.Tool) -> None:
        """Init the class."""
        super().__init__(hass=hass, id="test", name="Test")
        self.tool = tool

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt="Test prompt.",
            llm_context=llm_context,
            tools=[self.tool],
        )


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


@pytest.fixture
def state_tool() -> GetStateTool:
    """Return the test tool."""
    return GetStateTool()


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant, state_tool: GetStateTool) -> None:
    """Set up Code Mode and the test API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    llm.async_register_api(hass, TestAPI(hass, state_tool))


@pytest.fixture
def conversation_id(hass: HomeAssistant) -> str:
    """Return the conversation ID of a chat session."""
    with chat_session.async_get_chat_session(hass, context=None) as session:
        return session.conversation_id


@pytest.fixture
async def api_instance(
    hass: HomeAssistant, llm_context: llm.LLMContext, conversation_id: str
) -> llm.APIInstance:
    """Return the Assist API and the test API with their tools as code."""
    return code_mode_api.async_create_api_instance(
        await llm.async_get_api(hass, [llm.LLM_API_ASSIST, "test"], llm_context),
        conversation_id,
    )


async def _execute(api_instance: llm.APIInstance, code: str) -> llm.ToolResult:
    """Run code with the execute tool."""
    return await api_instance.async_call_tool(llm.ToolInput("execute", {"code": code}))


async def _search(api_instance: llm.APIInstance, query: str) -> list[str]:
    """Return the declarations that the search tool finds."""
    result = await api_instance.async_call_tool(
        llm.ToolInput("search", {"query": query})
    )
    functions: list[str] = result.data["functions"]
    return functions


async def test_api_instance(api_instance: llm.APIInstance) -> None:
    """Test the API has two tools and a prompt without the functions."""
    assert [tool.name for tool in api_instance.tools] == ["search", "execute"]
    assert api_instance.api.id == "assist|test"
    assert "Test prompt." in api_instance.api_prompt
    assert "`search` tool" in api_instance.api_prompt
    assert "async def" not in api_instance.api_prompt


async def test_search(api_instance: llm.APIInstance) -> None:
    """Test search returns the declarations of the functions that match."""
    assert (await _search(api_instance, "state of an entity"))[0] == (
        """async def test__get_state(
    *,
    entity_id: str,  # The entity
    attributes: list[Literal['brightness', 'color']] = None,
    retries: int | None = None,
) -> dict:
    \"\"\"Read a light. Get the state of an entity\"\"\""""
    )
    # The title of a tool is part of the search.
    assert (await _search(api_instance, "read light"))[0].startswith(
        "async def test__get_state("
    )
    assert (await _search(api_instance, "GetDateTime"))[0] == (
        "async def llm__GetDateTime() -> dict:\n"
        '    """Get date and time. Provides the current date and time."""'
    )
    assert await _search(api_instance, "vacuum") == []


@pytest.mark.parametrize(
    ("title", "query"),
    [
        ("Включить свет", "включить свет"),
        ("Küche aufräumen", "küche"),
        ("打开灯", "打开灯"),
    ],
)
async def test_search_other_languages(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    conversation_id: str,
    title: str,
    query: str,
) -> None:
    """Test search finds a tool by a title that is not in English."""

    class TitledTool(llm.Tool):
        """Tool with a title, like a script that a user named."""

        name = "script__s1"
        integration = "test"

        @override
        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            """Return nothing."""
            return llm.ToolResult(data={})

    tool = TitledTool()
    tool.title = title
    api_instance = code_mode_api.async_create_api_instance(
        llm.APIInstance(
            api=TestAPI(hass, tool),
            api_prompt="",
            llm_context=llm_context,
            tools=[tool],
        ),
        conversation_id,
    )

    assert await _search(api_instance, query) == [
        f'async def script__s1() -> dict:\n    """{title}"""'
    ]
    assert await _search(api_instance, "vacuum") == []


async def test_nested_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext, conversation_id: str
) -> None:
    """Test the declaration shows the keys of dict parameters."""

    class MemoryTool(llm.Tool):
        """Tool with nested parameters."""

        name = "save_memory"
        description = "Save a memory"
        integration = "test"
        parameters = probatio.Schema(
            {
                probatio.Required("context"): {
                    probatio.Required("fact"): str,
                    probatio.Optional("tags"): [str],
                    probatio.Optional("source"): {
                        probatio.Required("url"): str,
                        probatio.Optional("meta"): {
                            probatio.Optional("deep"): {
                                probatio.Optional("deeper"): str
                            }
                        },
                    },
                },
                probatio.Optional("items"): [{probatio.Required("id"): int}],
            }
        )

        @override
        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            """Return the fact."""
            return llm.ToolResult(data={"saved": tool_input.tool_args["context"]})

    api_instance = code_mode_api.async_create_api_instance(
        llm.APIInstance(
            api=TestAPI(hass, MemoryTool()),
            api_prompt="",
            llm_context=llm_context,
            tools=[MemoryTool()],
        ),
        conversation_id,
    )

    assert (await _search(api_instance, "memory"))[0].startswith(
        """async def save_memory(
    *,
    context: {"fact": str, "tags"?: list[str], "source"?: {"url": str, "meta"?: {"deep"?: dict}}},
    items: list[{"id": int}] = None,
) -> dict:"""
    )

    result = await _execute(
        api_instance, 'await save_memory(context={"fact": "Likes tea"})'
    )
    assert result.data["result"] == {"saved": {"fact": "Likes tea"}}


async def test_execute_calls_tools(
    api_instance: llm.APIInstance, state_tool: GetStateTool
) -> None:
    """Test the code calls tools from every wrapped API in parallel."""
    result = await _execute(
        api_instance,
        """
import asyncio
ids = [f"light.room_{i}" for i in range(10)]
states = await asyncio.gather(*[test__get_state(entity_id=i) for i in ids])
now = await llm__GetDateTime()
print("checked", len(states))
{"on": [s["entity_id"] for s in states if s["state"] == "on"], "has_date": "date" in now}
""",
    )

    assert result.error is False
    assert result.data == {
        "result": {"on": ["light.room_0", "light.room_5"], "has_date": True},
        "output": "checked 10\n",
    }
    assert len(state_tool.calls) == 10


async def test_modules_without_import(api_instance: llm.APIInstance) -> None:
    """Test the code can use the listed modules without an import."""
    result = await _execute(
        api_instance,
        """
states = await asyncio.gather(
    test__get_state(entity_id="light.room_0"), test__get_state(entity_id="light.room_1")
)
[
    [state["state"] for state in states],
    json.dumps({"a": 1}),
    math.floor(2.5),
    str(datetime.date(2026, 1, 2)),
    re.sub("a", "b", "aa"),
]
""",
    )

    assert result.data["result"] == [["on", "off"], '{"a": 1}', 2, "2026-01-02", "bb"]


@pytest.mark.parametrize(
    ("entity_id", "message"),
    [
        ("light.broken", "HomeAssistantError: Light is broken"),
        # A tool result with the error flag.
        ("light.failed", '{"reason": "No power"}'),
    ],
)
async def test_tool_error_raises_in_code(
    api_instance: llm.APIInstance, entity_id: str, message: str
) -> None:
    """Test a failing tool raises an exception that the code can catch."""
    result = await _execute(
        api_instance,
        f"""
try:
    await test__get_state(entity_id="{entity_id}")
except Exception as err:
    caught = [type(err).__name__, str(err)]
caught
""",
    )
    assert result.data["result"] == ["Exception", message]

    result = await _execute(
        api_instance, f'await test__get_state(entity_id="{entity_id}")'
    )
    assert result.error is True
    assert result.data["error"] == f"Exception: {message}"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("await execute(code='1')", "NameError"),
        ("open('/etc/passwd').read()", "PermissionError"),
        ("import socket", "ModuleNotFoundError"),
        ("().__class__", "AttributeError"),
        ("x = 'a' * 10**10", "MemoryError"),
        ("1 +", "Expected an expression"),
    ],
)
async def test_sandbox(api_instance: llm.APIInstance, code: str, error: str) -> None:
    """Test the sandbox blocks access and reports errors."""
    result = await _execute(api_instance, code)

    assert result.error is True
    assert error in result.data["error"]


async def test_error_size_limit(api_instance: llm.APIInstance) -> None:
    """Test a large error message of the code is cut."""
    result = await _execute(api_instance, "raise ValueError('a' * 1000000)")

    assert result.error is True
    assert result.data["error"].startswith("ValueError: aaa")
    assert len(result.data["error"]) == code_mode_api.MAX_ERROR_SIZE


async def test_cpu_limit(api_instance: llm.APIInstance) -> None:
    """Test a busy loop is stopped."""
    with patch.dict(code_mode_api.LIMITS, {"max_feed_duration_secs": 0.1}):
        result = await _execute(api_instance, "while True: pass")

    assert result.error is True
    assert "TimeoutError" in result.data["error"]


async def test_wall_clock_limit(api_instance: llm.APIInstance) -> None:
    """Test a slow tool call is stopped."""
    with patch.object(code_mode_api, "TIMEOUT", 0.1):
        result = await _execute(
            api_instance, 'await test__get_state(entity_id="light.slow")'
        )

    assert result.error is True
    assert result.data == {"error": "Timeout", "output": ""}


async def test_sandbox_cannot_start(api_instance: llm.APIInstance) -> None:
    """Test an error is returned when the sandbox process cannot start."""
    with patch.object(code_mode_api, "AsyncMonty", autospec=True) as mock_pool:
        mock_pool.return_value.__aenter__.side_effect = OSError("No binary")
        result = await _execute(api_instance, "1")

    assert result.error is True
    assert result.data == {"error": "No binary", "output": ""}


def _sandbox_count() -> int:
    """Return the number of running sandbox processes."""
    return sum(
        child.name() == "monty" for child in psutil.Process().children(recursive=True)
    )


async def test_sandbox_lives_with_chat_session(
    hass: HomeAssistant, api_instance: llm.APIInstance
) -> None:
    """Test the sandbox stays between runs and stops with the chat session."""
    assert _sandbox_count() == 0

    for value in (1, 2):
        result = await _execute(api_instance, str(value))
        assert result.data["result"] == value
        # The sandbox stays for the next run of the conversation.
        assert _sandbox_count() == 1

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=2),
    )
    await hass.async_block_till_done()

    assert _sandbox_count() == 0


async def test_sandbox_limit(
    hass: HomeAssistant, api_instance: llm.APIInstance
) -> None:
    """Test runs wait for a sandbox when the maximum number is in use."""
    sandbox_counts: list[int] = []

    async def run(value: int) -> int:
        result = await _execute(
            api_instance,
            f'await test__get_state(entity_id="light.room_{value}")\n{value}',
        )
        sandbox_counts.append(_sandbox_count())
        return result.data["result"]

    with patch.object(code_mode_api, "MAX_SANDBOXES", 2):
        assert await asyncio.gather(*[run(value) for value in range(6)]) == [
            0,
            1,
            2,
            3,
            4,
            5,
        ]
    assert max(sandbox_counts) == 2

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=2),
    )
    await hass.async_block_till_done()

    assert _sandbox_count() == 0
    assert hass.data[code_mode_api.DATA_SANDBOXES].conversation_ids == set()


async def test_sandbox_stops_with_home_assistant(
    hass: HomeAssistant, api_instance: llm.APIInstance
) -> None:
    """Test the sandbox stops when Home Assistant stops."""
    await _execute(api_instance, "1")
    assert _sandbox_count() == 1

    await hass.async_stop()

    assert _sandbox_count() == 0


async def test_result_is_json(api_instance: llm.APIInstance) -> None:
    """Test the result is converted with the JSON encoder of Home Assistant."""
    result = await _execute(api_instance, "{'items': (1, 2), 'ids': {1}, 5: 'five'}")

    assert result.data["result"] == {"items": [1, 2], "ids": [1], "5": "five"}


@pytest.mark.parametrize("code", ["{(1, 2): None}", "2**100", "type(1)", "b'abc'"])
async def test_result_is_not_json(api_instance: llm.APIInstance, code: str) -> None:
    """Test a result that JSON cannot represent gives an error."""
    result = await _execute(api_instance, f"print('ran')\n{code}")

    assert result.error is True
    assert result.data["error"].startswith("The result cannot be converted to JSON: ")
    assert result.data["output"] == "ran\n"


async def test_python_names_are_unique(
    hass: HomeAssistant, llm_context: llm.LLMContext, conversation_id: str
) -> None:
    """Test tools whose names give the same Python name stay separate."""

    class NameTool(llm.Tool):
        """Tool that returns its name."""

        integration = "test"

        def __init__(self, name: str) -> None:
            """Init the class."""
            self.name = name

        @override
        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            """Return the name of the tool."""
            return llm.ToolResult(data={"name": self.name})

    api_instance = code_mode_api.async_create_api_instance(
        llm.APIInstance(
            api=TestAPI(hass, NameTool("unused")),
            api_prompt="",
            llm_context=llm_context,
            tools=[
                NameTool("foo-bar"),
                NameTool("foo_bar"),
                NameTool("foo.bar"),
                NameTool("class"),
                NameTool("123status"),
                NameTool("len"),
                NameTool("asyncio"),
            ],
        ),
        conversation_id,
    )

    names = (
        "foo_bar",
        "foo_bar_2",
        "foo_bar_3",
        "tool_class",
        "tool_123status",
        "tool_len",
        "tool_asyncio",
    )
    for name in names:
        assert any(
            declaration.startswith(f"async def {name}() -> dict:")
            for declaration in await _search(api_instance, name)
        )
    result = await _execute(
        api_instance, f"[{', '.join(f'await {name}()' for name in names)}]"
    )
    assert result.data["result"] == [
        {"name": "foo-bar"},
        {"name": "foo_bar"},
        {"name": "foo.bar"},
        {"name": "class"},
        {"name": "123status"},
        {"name": "len"},
        {"name": "asyncio"},
    ]


@pytest.mark.parametrize("tool_args", [{}, {"code": None}, {"code": "1", "extra": 1}])
async def test_invalid_arguments(
    api_instance: llm.APIInstance, tool_args: dict[str, Any]
) -> None:
    """Test invalid arguments raise the error that the chat log handles."""
    with pytest.raises(probatio.Invalid):
        await api_instance.async_call_tool(llm.ToolInput("execute", tool_args))


async def test_custom_serializer_is_kept(
    hass: HomeAssistant, llm_context: llm.LLMContext, conversation_id: str
) -> None:
    """Test the API instance keeps the serializer for schemas of the provider."""
    assist = await llm.async_get_api(hass, llm.LLM_API_ASSIST, llm_context)
    assert assist.custom_serializer is not None

    api_instance = code_mode_api.async_create_api_instance(assist, conversation_id)

    assert api_instance.custom_serializer is assist.custom_serializer


async def test_tools_get_current_context(
    api_instance: llm.APIInstance, state_tool: GetStateTool
) -> None:
    """Test tools get the context of the turn that runs the code."""
    # The chat log replaces the context of a kept API instance for each turn.
    api_instance.llm_context = llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="nl",
        assistant="conversation",
        device_id=None,
    )

    await _execute(api_instance, 'await test__get_state(entity_id="light.room_1")')

    assert state_tool.llm_contexts == [api_instance.llm_context]
