"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

import codecs
from collections.abc import AsyncGenerator, Callable
from dataclasses import replace
from typing import Any, Literal, cast

from google.genai.errors import APIError
from google.genai.types import (
    AutomaticFunctionCallingConfig,
    Content,
    FunctionDeclaration,
    GenerateContentConfig,
    GenerateContentResponse,
    GoogleSearch,
    HarmCategory,
    Part,
    SafetySetting,
    Schema,
    Tool,
)
from voluptuous_openapi import convert

from homeassistant.components import assist_pipeline, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, intent, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10

ERROR_GETTING_RESPONSE = (
    "Sorry, I had a problem getting a response from Google Generative AI."
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = GoogleGenerativeAIConversationEntity(config_entry)
    async_add_entities([agent])


SUPPORTED_SCHEMA_KEYS = {
    # Gemini API does not support all of the OpenAPI schema
    # SoT: https://ai.google.dev/api/caching#Schema
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "max_items",
    "min_items",
    "properties",
    "required",
    "items",
}


def _camel_to_snake(name: str) -> str:
    """Convert camel case to snake case."""
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")


def _format_schema(schema: dict[str, Any]) -> Schema:
    """Format the schema to be compatible with Gemini API."""
    if subschemas := schema.get("allOf"):
        for subschema in subschemas:  # Gemini API does not support allOf keys
            if "type" in subschema:  # Fallback to first subschema with 'type' field
                return _format_schema(subschema)
        return _format_schema(
            subschemas[0]
        )  # Or, if not found, to any of the subschemas

    result = {}
    for key, val in schema.items():
        key = _camel_to_snake(key)
        if key not in SUPPORTED_SCHEMA_KEYS:
            continue
        if key == "type":
            val = val.upper()
        elif key == "format":
            # Gemini API does not support all formats, see: https://ai.google.dev/api/caching#Schema
            # formats that are not supported are ignored
            if schema.get("type") == "string" and val not in ("enum", "date-time"):
                continue
            if schema.get("type") == "number" and val not in ("float", "double"):
                continue
            if schema.get("type") == "integer" and val not in ("int32", "int64"):
                continue
            if schema.get("type") not in ("string", "number", "integer"):
                continue
        elif key == "items":
            val = _format_schema(val)
        elif key == "properties":
            val = {k: _format_schema(v) for k, v in val.items()}
        result[key] = val

    if result.get("enum") and result.get("type") != "STRING":
        # enum is only allowed for STRING type. This is safe as long as the schema
        # contains vol.Coerce for the respective type, for example:
        # vol.All(vol.Coerce(int), vol.In([1, 2, 3]))
        result["type"] = "STRING"
        result["enum"] = [str(item) for item in result["enum"]]

    if result.get("type") == "OBJECT" and not result.get("properties"):
        # An object with undefined properties is not supported by Gemini API.
        # Fallback to JSON string. This will probably fail for most tools that want it,
        # but we don't have a better fallback strategy so far.
        result["properties"] = {"json": {"type": "STRING"}}
        result["required"] = []
    return cast(Schema, result)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> Tool:
    """Format tool specification."""

    if tool.parameters.schema:
        parameters = _format_schema(
            convert(tool.parameters, custom_serializer=custom_serializer)
        )
    else:
        parameters = None

    return Tool(
        function_declarations=[
            FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=parameters,
            )
        ]
    )


def _escape_decode(value: Any) -> Any:
    """Recursively call codecs.escape_decode on all values."""
    if isinstance(value, str):
        return codecs.escape_decode(bytes(value, "utf-8"))[0].decode("utf-8")  # type: ignore[attr-defined]
    if isinstance(value, list):
        return [_escape_decode(item) for item in value]
    if isinstance(value, dict):
        return {k: _escape_decode(v) for k, v in value.items()}
    return value


def _create_google_tool_response_parts(
    parts: list[conversation.ToolResultContent],
) -> list[Part]:
    """Create Google tool response parts."""
    return [
        Part.from_function_response(
            name=tool_result.tool_name, response=tool_result.tool_result
        )
        for tool_result in parts
    ]


def _create_google_tool_response_content(
    content: list[conversation.ToolResultContent],
) -> Content:
    """Create a Google tool response content."""
    return Content(
        role="user",
        parts=_create_google_tool_response_parts(content),
    )


def _convert_content(
    content: conversation.UserContent
    | conversation.AssistantContent
    | conversation.SystemContent,
) -> Content:
    """Convert HA content to Google content."""
    if content.role != "assistant" or not content.tool_calls:
        role = "model" if content.role == "assistant" else content.role
        return Content(
            role=role,
            parts=[
                Part.from_text(text=content.content if content.content else ""),
            ],
        )

    # Handle the Assistant content with tool calls.
    assert type(content) is conversation.AssistantContent
    parts: list[Part] = []

    if content.content:
        parts.append(Part.from_text(text=content.content))

    if content.tool_calls:
        parts.extend(
            [
                Part.from_function_call(
                    name=tool_call.tool_name,
                    args=_escape_decode(tool_call.tool_args),
                )
                for tool_call in content.tool_calls
            ]
        )

    return Content(role="model", parts=parts)


async def _transform_stream(
    result: AsyncGenerator[GenerateContentResponse],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    new_message = True
    try:
        async for response in result:
            LOGGER.debug("Received response chunk: %s", response)
            chunk: conversation.AssistantContentDeltaDict = {}

            if new_message:
                chunk["role"] = "assistant"
                new_message = False

            # According to the API docs, this would mean no candidate is returned, so we can safely throw an error here.
            if response.prompt_feedback or not response.candidates:
                reason = (
                    response.prompt_feedback.block_reason_message
                    if response.prompt_feedback
                    else "unknown"
                )
                raise HomeAssistantError(
                    f"The message got blocked due to content violations, reason: {reason}"
                )

            candidate = response.candidates[0]

            if (
                candidate.finish_reason is not None
                and candidate.finish_reason == "STOP"
            ):
                # End of the message
                new_message = True
            elif candidate.finish_reason is not None:
                # The message ended due to a content error as explained in: https://ai.google.dev/api/generate-content#FinishReason
                LOGGER.error(
                    "Error in Google Generative AI response: %s, see: https://ai.google.dev/api/generate-content#FinishReason",
                    candidate.finish_reason,
                )
                raise HomeAssistantError(
                    f"Sorry, I had a problem getting a response from Google Generative AI. Reason: {candidate.finish_reason}"
                )

            response_parts = (
                candidate.content.parts
                if candidate.content is not None and candidate.content.parts is not None
                else []
            )

            content = "".join([part.text for part in response_parts if part.text])
            tool_calls = []
            for part in response_parts:
                if not part.function_call:
                    continue
                tool_call = part.function_call
                tool_name = tool_call.name if tool_call.name else ""
                tool_args = _escape_decode(tool_call.args)
                tool_calls.append(
                    llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
                )

            if tool_calls:
                chunk["tool_calls"] = tool_calls

            chunk["content"] = content
            yield chunk
    except (
        APIError,
        ValueError,
    ) as err:
        LOGGER.error("Error sending message: %s %s", type(err), err)
        if isinstance(err, APIError):
            message = err.message
        else:
            message = type(err).__name__
        error = f"Sorry, I had a problem talking to Google Generative AI: {message}"
        raise HomeAssistantError(error) from err


class GoogleGenerativeAIConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Google Generative AI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._genai_client = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Google",
            model="Generative AI",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if self.entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        assist_pipeline.async_migrate_engine(
            self.hass, "conversation", self.entry.entry_id, self.entity_id
        )
        conversation.async_set_agent(self.hass, self.entry, self)
        self.entry.async_on_unload(
            self.entry.add_update_listener(self._async_entry_update_listener)
        )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    def _fix_tool_name(self, tool_name: str) -> str:
        """Fix tool name if needed."""
        # The Gemini 2.0+ tokenizer seemingly has a issue with the HassListAddItem tool
        # name. This makes sure when it incorrectly changes the name, that we change it
        # back for HA to call.
        return tool_name if tool_name != "HasListAddItem" else "HassListAddItem"

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
        options = self.entry.options

        try:
            await chat_log.async_update_llm_data(
                DOMAIN,
                user_input,
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        tools: list[Tool | Callable[..., Any]] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        # Using search grounding allows the model to retrieve information from the web,
        # however, it may interfere with how the model decides to use some tools, or entities
        # for example weather entity may be disregarded if the model chooses to Google it.
        if options.get(CONF_USE_GOOGLE_SEARCH_TOOL) is True:
            tools = tools or []
            tools.append(Tool(google_search=GoogleSearch()))

        model_name = self.entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        # Gemini 1.0 doesn't support system_instruction while 1.5 does.
        # Assume future versions will support it (if not, the request fails with a
        # clear message at which point we can fix).
        supports_system_instruction = (
            "gemini-1.0" not in model_name and "gemini-pro" not in model_name
        )

        prompt_content = cast(
            conversation.SystemContent,
            chat_log.content[0],
        )

        if prompt_content.content:
            prompt = prompt_content.content
        else:
            raise HomeAssistantError("Invalid prompt content")

        messages: list[Content] = []

        # Google groups tool results, we do not. Group them before sending.
        tool_results: list[conversation.ToolResultContent] = []

        for chat_content in chat_log.content[1:-1]:
            if chat_content.role == "tool_result":
                tool_results.append(chat_content)
                continue

            if (
                not isinstance(chat_content, conversation.ToolResultContent)
                and chat_content.content == ""
            ):
                # Skipping is not possible since the number of function calls need to match the number of function responses
                # and skipping one would mean removing the other and hence this would prevent a proper chat log
                chat_content = replace(chat_content, content=" ")

            if tool_results:
                messages.append(_create_google_tool_response_content(tool_results))
                tool_results.clear()

            messages.append(_convert_content(chat_content))

        # The SDK requires the first message to be a user message
        # This is not the case if user used `start_conversation`
        # Workaround from https://github.com/googleapis/python-genai/issues/529#issuecomment-2740964537
        if messages and messages[0].role != "user":
            messages.insert(
                0,
                Content(role="user", parts=[Part.from_text(text=" ")]),
            )

        if tool_results:
            messages.append(_create_google_tool_response_content(tool_results))
        generateContentConfig = GenerateContentConfig(
            temperature=self.entry.options.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            ),
            top_k=self.entry.options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
            top_p=self.entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            max_output_tokens=self.entry.options.get(
                CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
            ),
            safety_settings=[
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=self.entry.options.get(
                        CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=self.entry.options.get(
                        CONF_HARASSMENT_BLOCK_THRESHOLD,
                        RECOMMENDED_HARM_BLOCK_THRESHOLD,
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=self.entry.options.get(
                        CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=self.entry.options.get(
                        CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
            ],
            tools=tools or None,
            system_instruction=prompt if supports_system_instruction else None,
            automatic_function_calling=AutomaticFunctionCallingConfig(
                disable=True, maximum_remote_calls=None
            ),
        )

        if not supports_system_instruction:
            messages = [
                Content(role="user", parts=[Part.from_text(text=prompt)]),
                Content(role="model", parts=[Part.from_text(text="Ok")]),
                *messages,
            ]
        chat = self._genai_client.aio.chats.create(
            model=model_name, history=messages, config=generateContentConfig
        )
        chat_request: str | list[Part] = user_input.text
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            chat_response_generator = await chat.send_message_stream(
                message=chat_request
            )
            chat_request = _create_google_tool_response_parts(
                [
                    content
                    async for content in chat_log.async_add_delta_content_stream(
                        user_input.agent_id,
                        _transform_stream(chat_response_generator),
                    )
                    if isinstance(content, conversation.ToolResultContent)
                ]
            )

            if not chat_log.unresponded_tool_results:
                break

        response = intent.IntentResponse(language=user_input.language)
        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise TypeError(
                f"Unexpected last message type: {type(chat_log.content[-1])}"
            )
        response.async_set_speech(chat_log.content[-1].content or "")
        return conversation.ConversationResult(
            response=response,
            conversation_id=chat_log.conversation_id,
            continue_conversation=chat_log.continue_conversation,
        )

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
