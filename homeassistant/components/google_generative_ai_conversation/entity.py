"""Conversation support for the Google Generative AI Conversation integration."""

from __future__ import annotations

import asyncio
import base64
import codecs
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from dataclasses import dataclass, replace
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from google.genai import Client
from google.genai.errors import APIError, ClientError
from google.genai.types import (
    AutomaticFunctionCallingConfig,
    Content,
    ContentDict,
    File,
    FileState,
    FunctionDeclaration,
    GenerateContentConfig,
    GenerateContentResponse,
    GoogleSearch,
    HarmCategory,
    Part,
    PartUnionDict,
    SafetySetting,
    Schema,
    ThinkingConfig,
    Tool,
    ToolListUnion,
)
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DOMAIN,
    FILE_POLLING_INTERVAL_SECONDS,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
    TIMEOUT_MILLIS,
)

if TYPE_CHECKING:
    from . import GoogleGenerativeAIConfigEntry

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10

ERROR_GETTING_RESPONSE = (
    "Sorry, I had a problem getting a response from Google Generative AI."
)


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


@dataclass(slots=True)
class PartDetails:
    """Additional data for a content part."""

    part_type: Literal["text", "thought", "function_call"]
    """The part type for which this data is relevant for."""

    index: int
    """Start position or number of the tool."""

    length: int = 0
    """Length of the relevant data."""

    thought_signature: str | None = None
    """Base64 encoded thought signature, if available."""


@dataclass(slots=True)
class ContentDetails:
    """Native data for AssistantContent."""

    part_details: list[PartDetails]


def _convert_content(
    content: (
        conversation.UserContent
        | conversation.AssistantContent
        | conversation.SystemContent
    ),
) -> Content:
    """Convert HA content to Google content."""
    if content.role != "assistant":
        return Content(
            role=content.role,
            parts=[Part.from_text(text=content.content if content.content else "")],
        )

    # Handle the Assistant content with tool calls.
    assert type(content) is conversation.AssistantContent
    parts: list[Part] = []
    part_details: list[PartDetails] = (
        content.native.part_details
        if isinstance(content.native, ContentDetails)
        else []
    )
    details: PartDetails | None = None

    if content.content:
        index = 0
        for details in part_details:
            if details.part_type == "text":
                if index < details.index:
                    parts.append(
                        Part.from_text(text=content.content[index : details.index])
                    )
                    index = details.index
                parts.append(
                    Part.from_text(
                        text=content.content[index : index + details.length],
                    )
                )
                if details.thought_signature:
                    parts[-1].thought_signature = base64.b64decode(
                        details.thought_signature
                    )
                index += details.length
        if index < len(content.content):
            parts.append(Part.from_text(text=content.content[index:]))

    if content.thinking_content:
        index = 0
        for details in part_details:
            if details.part_type == "thought":
                if index < details.index:
                    parts.append(
                        Part.from_text(
                            text=content.thinking_content[index : details.index]
                        )
                    )
                    parts[-1].thought = True
                    index = details.index
                parts.append(
                    Part.from_text(
                        text=content.thinking_content[index : index + details.length],
                    )
                )
                parts[-1].thought = True
                if details.thought_signature:
                    parts[-1].thought_signature = base64.b64decode(
                        details.thought_signature
                    )
                index += details.length
        if index < len(content.thinking_content):
            parts.append(Part.from_text(text=content.thinking_content[index:]))
            parts[-1].thought = True

    if content.tool_calls:
        for index, tool_call in enumerate(content.tool_calls):
            parts.append(
                Part.from_function_call(
                    name=tool_call.tool_name,
                    args=_escape_decode(tool_call.tool_args),
                )
            )
            if details := next(
                (
                    d
                    for d in part_details
                    if d.part_type == "function_call" and d.index == index
                ),
                None,
            ):
                if details.thought_signature:
                    parts[-1].thought_signature = base64.b64decode(
                        details.thought_signature
                    )

    return Content(role="model", parts=parts)


async def _transform_stream(
    result: AsyncIterator[GenerateContentResponse],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    new_message = True
    part_details: list[PartDetails] = []
    try:
        async for response in result:
            LOGGER.debug("Received response chunk: %s", response)

            if new_message:
                if part_details:
                    yield {"native": ContentDetails(part_details=part_details)}
                    part_details = []
                yield {"role": "assistant"}
                new_message = False
                content_index = 0
                thinking_content_index = 0
                tool_call_index = 0

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
                and candidate.finish_reason != "STOP"
            ):
                # The message ended due to a content error as explained in: https://ai.google.dev/api/generate-content#FinishReason
                LOGGER.error(
                    "Error in Google Generative AI response: %s, see: https://ai.google.dev/api/generate-content#FinishReason",
                    candidate.finish_reason,
                )
                raise HomeAssistantError(
                    f"{ERROR_GETTING_RESPONSE} Reason: {candidate.finish_reason}"
                )

            response_parts = (
                candidate.content.parts
                if candidate.content is not None and candidate.content.parts is not None
                else []
            )

            for part in response_parts:
                chunk: conversation.AssistantContentDeltaDict = {}

                if part.text:
                    if part.thought:
                        chunk["thinking_content"] = part.text
                        if part.thought_signature:
                            part_details.append(
                                PartDetails(
                                    part_type="thought",
                                    index=thinking_content_index,
                                    length=len(part.text),
                                    thought_signature=base64.b64encode(
                                        part.thought_signature
                                    ).decode("utf-8"),
                                )
                            )
                        thinking_content_index += len(part.text)
                    else:
                        chunk["content"] = part.text
                        if part.thought_signature:
                            part_details.append(
                                PartDetails(
                                    part_type="text",
                                    index=content_index,
                                    length=len(part.text),
                                    thought_signature=base64.b64encode(
                                        part.thought_signature
                                    ).decode("utf-8"),
                                )
                            )
                        content_index += len(part.text)

                if part.function_call:
                    tool_call = part.function_call
                    tool_name = tool_call.name if tool_call.name else ""
                    tool_args = _escape_decode(tool_call.args)
                    chunk["tool_calls"] = [
                        llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
                    ]
                    if part.thought_signature:
                        part_details.append(
                            PartDetails(
                                part_type="function_call",
                                index=tool_call_index,
                                thought_signature=base64.b64encode(
                                    part.thought_signature
                                ).decode("utf-8"),
                            )
                        )

                yield chunk

        if part_details:
            yield {"native": ContentDetails(part_details=part_details)}

    except (
        APIError,
        ValueError,
    ) as err:
        LOGGER.error("Error sending message: %s %s", type(err), err)
        if isinstance(err, APIError):
            message = err.message
        else:
            message = type(err).__name__
        error = f"{ERROR_GETTING_RESPONSE}: {message}"
        raise HomeAssistantError(error) from err


class GoogleGenerativeAILLMBaseEntity(Entity):
    """Google Generative AI base entity."""

    def __init__(
        self,
        entry: GoogleGenerativeAIConfigEntry,
        subentry: ConfigSubentry,
        default_model: str = RECOMMENDED_CHAT_MODEL,
    ) -> None:
        """Initialize the agent."""
        self.entry = entry
        self.subentry = subentry
        self._attr_name = subentry.title
        self._genai_client = entry.runtime_data
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Google",
            model=subentry.data.get(CONF_CHAT_MODEL, default_model).split("/")[-1],
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data

        tools: ToolListUnion | None = None
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

        model_name = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        # Avoid INVALID_ARGUMENT Developer instruction is not enabled for <model>
        supports_system_instruction = (
            "gemma" not in model_name
            and "gemini-2.0-flash-preview-image-generation" not in model_name
        )

        prompt_content = cast(
            conversation.SystemContent,
            chat_log.content[0],
        )

        if prompt_content.content:
            prompt = prompt_content.content
        else:
            raise HomeAssistantError("Invalid prompt content")

        messages: list[Content | ContentDict] = []

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
        if messages and (
            (isinstance(messages[0], Content) and messages[0].role != "user")
            or (isinstance(messages[0], dict) and messages[0]["role"] != "user")
        ):
            messages.insert(
                0,
                Content(role="user", parts=[Part.from_text(text=" ")]),
            )

        if tool_results:
            messages.append(_create_google_tool_response_content(tool_results))
        generateContentConfig = self.create_generate_content_config()
        generateContentConfig.tools = tools or None
        generateContentConfig.system_instruction = (
            prompt if supports_system_instruction else None
        )
        generateContentConfig.automatic_function_calling = (
            AutomaticFunctionCallingConfig(disable=True, maximum_remote_calls=None)
        )
        if structure:
            generateContentConfig.response_mime_type = "application/json"
            generateContentConfig.response_schema = _format_schema(
                convert(
                    structure,
                    custom_serializer=(
                        chat_log.llm_api.custom_serializer
                        if chat_log.llm_api
                        else llm.selector_serializer
                    ),
                )
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
        user_message = chat_log.content[-1]
        assert isinstance(user_message, conversation.UserContent)
        chat_request: list[PartUnionDict] = [user_message.content]
        if user_message.attachments:
            chat_request.extend(
                await async_prepare_files_for_prompt(
                    self.hass,
                    self._genai_client,
                    [(a.path, a.mime_type) for a in user_message.attachments],
                )
            )

        # To prevent infinite loops, we limit the number of iterations
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                chat_response_generator = await chat.send_message_stream(
                    message=chat_request
                )
            except (
                APIError,
                ClientError,
                ValueError,
            ) as err:
                LOGGER.error("Error sending message: %s %s", type(err), err)
                error = ERROR_GETTING_RESPONSE
                raise HomeAssistantError(error) from err

            chat_request = list(
                _create_google_tool_response_parts(
                    [
                        content
                        async for content in chat_log.async_add_delta_content_stream(
                            self.entity_id,
                            _transform_stream(chat_response_generator),
                        )
                        if isinstance(content, conversation.ToolResultContent)
                    ]
                )
            )

            if not chat_log.unresponded_tool_results:
                break

    def create_generate_content_config(self) -> GenerateContentConfig:
        """Create the GenerateContentConfig for the LLM."""
        options = self.subentry.data
        model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        thinking_config: ThinkingConfig | None = None
        if model.startswith("gemini-2.5") and not model.endswith(
            ("tts", "image", "image-preview")
        ):
            thinking_config = ThinkingConfig(include_thoughts=True)

        return GenerateContentConfig(
            temperature=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
            top_k=options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
            top_p=options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            max_output_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            safety_settings=[
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=options.get(
                        CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=options.get(
                        CONF_HARASSMENT_BLOCK_THRESHOLD,
                        RECOMMENDED_HARM_BLOCK_THRESHOLD,
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=options.get(
                        CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=options.get(
                        CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
            ],
            thinking_config=thinking_config,
        )


async def async_prepare_files_for_prompt(
    hass: HomeAssistant, client: Client, files: list[tuple[Path, str | None]]
) -> list[File]:
    """Upload files so they can be attached to a prompt.

    Caller needs to ensure that the files are allowed.
    """

    def upload_files() -> list[File]:
        prompt_parts: list[File] = []
        for filename, mimetype in files:
            if not filename.exists():
                raise HomeAssistantError(f"`{filename}` does not exist")
            if mimetype is None:
                mimetype = mimetypes.guess_type(filename)[0]
            prompt_parts.append(
                client.files.upload(
                    file=filename,
                    config={
                        "mime_type": mimetype,
                        "display_name": filename.name,
                    },
                )
            )
        return prompt_parts

    async def wait_for_file_processing(uploaded_file: File) -> None:
        """Wait for file processing to complete."""
        first = True
        while uploaded_file.state in (
            FileState.STATE_UNSPECIFIED,
            FileState.PROCESSING,
        ):
            if first:
                first = False
            else:
                LOGGER.debug(
                    "Waiting for file `%s` to be processed, current state: %s",
                    uploaded_file.name,
                    uploaded_file.state,
                )
                await asyncio.sleep(FILE_POLLING_INTERVAL_SECONDS)

            uploaded_file = await client.aio.files.get(
                name=uploaded_file.name or "",
                config={"http_options": {"timeout": TIMEOUT_MILLIS}},
            )

        if uploaded_file.state == FileState.FAILED:
            raise HomeAssistantError(
                f"File `{uploaded_file.name}` processing failed, reason: {uploaded_file.error.message if uploaded_file.error else 'unknown'}"
            )

    prompt_parts = await hass.async_add_executor_job(upload_files)

    tasks = [
        asyncio.create_task(wait_for_file_processing(part))
        for part in prompt_parts
        if part.state != FileState.ACTIVE
    ]
    async with asyncio.timeout(TIMEOUT_MILLIS / 1000):
        await asyncio.gather(*tasks)

    return prompt_parts
