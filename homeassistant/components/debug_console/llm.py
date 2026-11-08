"""Python execution tools for the Home Assistant admin LLM API."""

from typing import override

import probatio

from homeassistant.components.http import KEY_HASS_REFRESH_TOKEN_ID
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import chat_session
from homeassistant.helpers.http import current_request
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)

from .const import DOMAIN
from .execution import async_execute
from .safeguards import async_log_llm_execution, async_warning_required
from .session import SessionNotFoundError, async_llm_session, async_mcp_session


class ExecutePythonTool(Tool):
    """Execute Python inside Home Assistant after explicit frontend consent."""

    name = "debug_console__repl"
    title = "Python REPL"
    description = (
        "Run Python in the running Home Assistant event loop with 'hass' object "
        "available. Supports top-level await and returns the last expression, "
        "printed output, and errors. Properties show as `(...)` because "
        "reading them can have side effects. Blocking sync calls must be "
        "wrapped in `await hass.async_add_executor_job(...)`. "
        "Sessions expire after 30 minutes of inactivity."
    )
    annotations = ToolAnnotations(
        read_only=False,
        destructive=True,
        idempotent=False,
        open_world=True,
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {probatio.Required("code", description="Python code to execute"): str}
    )

    def __init__(self, *, mcp: bool) -> None:
        """Select explicit MCP handles or automatic conversation sessions."""
        self._mcp = mcp
        if mcp:
            self.parameters = probatio.Schema(
                {
                    **self.parameters.schema,
                    probatio.Optional(
                        "session_id",
                        description=(
                            "Omit to start a new session; otherwise reuse the "
                            "session_id returned by a previous call."
                        ),
                    ): probatio.All(str, probatio.Length(min=1, max=64)),
                }
            )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Recheck authorization and consent before running any Python."""
        if (
            not (context := llm_context.context)
            or not context.user_id
            or not (user := await hass.auth.async_get_user(context.user_id))
            or not user.is_active
            or not user.is_admin
        ):
            raise Unauthorized(context=llm_context.context)

        if DOMAIN not in hass.config.components or async_warning_required(
            hass, user.id
        ):
            return ToolResult(
                data={
                    "error": (
                        "Python execution requires the user to accept the Debug console "
                        "warning in Settings > Tools > Debug console. Ask the user to "
                        "accept it in the Home Assistant UI, then retry this tool. "
                        "An agent cannot grant consent. See "
                        "https://www.home-assistant.io/integrations/debug_console"
                    )
                },
                error=True,
            )

        args = self.parameters(tool_input.tool_args)
        if self._mcp:
            request = current_request.get()
            if (
                request is None
                or not (credential_id := request.get(KEY_HASS_REFRESH_TOKEN_ID))
                or not (credential := hass.auth.async_get_refresh_token(credential_id))
                or credential.user.id != user.id
            ):
                raise Unauthorized(context=context)
            session_context = async_mcp_session(
                hass, user.id, credential_id, args.get("session_id")
            )
        else:
            conversation = chat_session.current_session.get()
            if conversation is None:
                return ToolResult(
                    data={"error": "The Python REPL requires an active conversation."},
                    error=True,
                )
            if conversation.user_id != user.id:
                raise Unauthorized(context=context)
            session_context = async_llm_session(
                hass,
                user.id,
                llm_context.platform,
                llm_context.agent_id,
                conversation.conversation_id,
            )

        try:
            async with session_context as session:
                async_log_llm_execution(
                    user, context, llm_context.platform, args["code"]
                )
                result = await async_execute(hass, session, args["code"])
        except SessionNotFoundError:
            return ToolResult(
                data={
                    "error": (
                        "The session_id is unknown or has expired. "
                        "Omit session_id to start a new session."
                    )
                },
                error=True,
            )

        if self._mcp:
            result = {"session_id": session.session_id, **result}
        return ToolResult(data=result, error="error" in result)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Expose the admin API tool regardless of consent so agents can retry after approval."""
    if (
        api_id != LLM_API_HOME_ASSISTANT
        or DOMAIN not in hass.config.components
        or not llm_context.context
        or not llm_context.context.user_id
    ):
        return None

    return LLMTools(tools=[ExecutePythonTool(mcp=llm_context.platform == "mcp_server")])
