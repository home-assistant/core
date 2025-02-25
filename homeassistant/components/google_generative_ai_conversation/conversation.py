"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

import codecs
from collections.abc import Callable
from typing import Any, Literal, cast

from google.genai.errors import APIError
from google.genai.types import (
    AutomaticFunctionCallingConfig,
    Content,
    FunctionDeclaration,
    GenerateContentConfig,
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
from homeassistant.helpers import chat_session, device_registry as dr, intent, llm
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    agent = GoogleGenerativeAIConversationEntity(config_entry)
    async_add_entities([agent])


SUPPORTED_SCHEMA_KEYS = {
    "min_items",
    "example",
    "property_ordering",
    "pattern",
    "minimum",
    "default",
    "any_of",
    "max_length",
    "title",
    "min_properties",
    "min_length",
    "max_items",
    "maximum",
    "nullable",
    "max_properties",
    "type",
    "description",
    "enum",
    "format",
    "items",
    "properties",
    "required",
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
        if key == "any_of":
            val = [_format_schema(subschema) for subschema in val]
        if key == "type":
            val = val.upper()
        if key == "items":
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


def _create_google_tool_response_content(
    content: list[conversation.ToolResultContent],
) -> Content:
    """Create a Google tool response content."""
    return Content(
        parts=[
            Part.from_function_response(
                name=tool_result.tool_name, response=tool_result.tool_result
            )
            for tool_result in content
        ]
    )


def _convert_content(
    content: conversation.UserContent
    | conversation.AssistantContent
    | conversation.SystemContent,
) -> Content:
    """Convert HA content to Google content."""
    if content.role != "assistant" or not content.tool_calls:  # type: ignore[union-attr]
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

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        with (
            chat_session.async_get_chat_session(
                self.hass, user_input.conversation_id
            ) as session,
            conversation.async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            return await self._async_handle_message(user_input, chat_log)

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
                # mypy doesn't like picking a type based on checking shared property 'role'
                tool_results.append(cast(conversation.ToolResultContent, chat_content))
                continue

            if tool_results:
                messages.append(_create_google_tool_response_content(tool_results))
                tool_results.clear()

            messages.append(
                _convert_content(
                    cast(
                        conversation.UserContent
                        | conversation.SystemContent
                        | conversation.AssistantContent,
                        chat_content,
                    )
                )
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
        chat_request: str | Content = user_input.text
        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                chat_response = await chat.send_message(message=chat_request)

                if chat_response.prompt_feedback:
                    raise HomeAssistantError(
                        f"The message got blocked due to content violations, reason: {chat_response.prompt_feedback.block_reason_message}"
                    )

            except (
                APIError,
                ValueError,
            ) as err:
                LOGGER.error("Error sending message: %s %s", type(err), err)
                error = f"Sorry, I had a problem talking to Google Generative AI: {err}"
                raise HomeAssistantError(error) from err

            response_parts = chat_response.candidates[0].content.parts
            if not response_parts:
                raise HomeAssistantError(
                    "Sorry, I had a problem getting a response from Google Generative AI."
                )
            content = " ".join(
                [part.text.strip() for part in response_parts if part.text]
            )

            tool_calls = []
            for part in response_parts:
                if not part.function_call:
                    continue
                tool_call = part.function_call
                tool_name = tool_call.name
                tool_args = _escape_decode(tool_call.args)
                tool_calls.append(
                    llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
                )

            chat_request = _create_google_tool_response_content(
                [
                    tool_response
                    async for tool_response in chat_log.async_add_assistant_content(
                        conversation.AssistantContent(
                            agent_id=user_input.agent_id,
                            content=content,
                            tool_calls=tool_calls or None,
                        )
                    )
                ]
            )

            if not tool_calls:
                break

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(
            " ".join([part.text.strip() for part in response_parts if part.text])
        )
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )

    async def _async_entry_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        # Reload as we update device info + entity name + supported features
        await hass.config_entries.async_reload(entry.entry_id)
