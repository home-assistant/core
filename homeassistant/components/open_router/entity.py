"""Base entity for Open Router."""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator, Callable
import json
from typing import TYPE_CHECKING, Any, Dict, Literal, NotRequired, TypedDict

import openai
from openai import BadRequestError
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)

# Handle ChatCompletionMessageFunctionToolCallParam separately
try:
    from openai.types.chat import ChatCompletionMessageFunctionToolCallParam
except ImportError:
    # Fallback for older versions
    ChatCompletionMessageFunctionToolCallParam = Dict[str, Any]

# Handle different OpenAI library versions for imports
try:
    from openai.types.chat import ChatCompletionFunctionToolParam
except ImportError:
    # Fallback for older versions - create a type alias
    ChatCompletionFunctionToolParam = Dict[str, Any]

try:
    from openai.types.chat.chat_completion_message_function_tool_call_param import Function
except ImportError:
    # Fallback for older versions
    class Function(TypedDict):
        name: str
        arguments: str

try:
    from openai.types.shared_params import FunctionDefinition
except ImportError:
    # Fallback for older versions  
    class FunctionDefinition(TypedDict):
        name: str
        description: NotRequired[str]
        parameters: NotRequired[Dict[str, Any]]

# Handle different OpenAI library versions
try:
    from openai.types.shared_params import ResponseFormatJSONSchema
    from openai.types.shared_params.response_format_json_schema import JSONSchema
except ImportError:
    # Fallback for older OpenAI library versions
    from typing import TypedDict
    
    class JSONSchema(TypedDict, total=False):
        """Fallback JSONSchema type."""
        name: str
        description: str | None
        schema: dict[str, Any]
        strict: bool | None
    
    class ResponseFormatJSONSchema(TypedDict):
        """Fallback ResponseFormatJSONSchema type."""
        type: Literal["json_schema"]
        json_schema: JSONSchema
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from . import OpenRouterConfigEntry
from .const import DOMAIN, LOGGER

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the schema to be compatible with OpenRouter API."""
    if schema["type"] == "object":
        if "properties" not in schema:
            return

        if "required" not in schema:
            schema["required"] = []

        # Ensure all properties are required
        for prop, prop_info in schema["properties"].items():
            _adjust_schema(prop_info)
            if prop not in schema["required"]:
                prop_info["type"] = [prop_info["type"], "null"]
                schema["required"].append(prop)

    elif schema["type"] == "array":
        if "items" not in schema:
            return

        _adjust_schema(schema["items"])


def _format_structured_output(
    name: str, schema: vol.Schema, llm_api: llm.APIInstance | None
) -> JSONSchema:
    """Format the schema to be compatible with OpenRouter API."""
    result: JSONSchema = {
        "name": name,
        "strict": True,
    }
    result_schema = convert(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )

    _adjust_schema(result_schema)

    result["schema"] = result_schema
    return result


def _format_tool(
    tool: llm.Tool,
    custom_serializer: Callable[[Any], Any] | None,
) -> ChatCompletionFunctionToolParam:
    """Format tool specification."""
    tool_spec = FunctionDefinition(
        name=tool.name,
        parameters=convert(tool.parameters, custom_serializer=custom_serializer),
    )
    if tool.description:
        tool_spec["description"] = tool.description
    
    # Create tool param compatible with both old and new OpenAI versions
    try:
        return ChatCompletionFunctionToolParam(type="function", function=tool_spec)
    except (TypeError, AttributeError):
        # Fallback to dict format for older versions
        return {"type": "function", "function": tool_spec}


def _convert_content_to_chat_message(
    content: conversation.Content,
) -> ChatCompletionMessageParam | None:
    """Convert any native chat message for this agent to the native format."""
    LOGGER.debug("_convert_content_to_chat_message=%s", content)
    if isinstance(content, conversation.ToolResultContent):
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=content.tool_call_id,
            content=json.dumps(content.tool_result),
        )

    role: Literal["user", "assistant", "system"] = content.role
    if role == "system" and content.content:
        return ChatCompletionSystemMessageParam(role="system", content=content.content)

    if role == "user":
        # Handle user messages with potential attachments
        if isinstance(content, conversation.UserContent) and content.attachments:
            # Create multi-part content with text and images
            message_parts = []
            
            # Add text content if present
            if content.content:
                message_parts.append({
                    "type": "text",
                    "text": content.content
                })
            
            # Add attachments (images, etc.)
            for attachment in content.attachments:
                # Debug: Log attachment structure
                LOGGER.info("=== ATTACHMENT DEBUG INFO ===")
                LOGGER.info("Attachment type: %s", type(attachment))
                LOGGER.info("Attachment attributes: %s", dir(attachment))
                
                # Log ALL attribute values
                for attr in dir(attachment):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(attachment, attr)
                            if callable(value):
                                LOGGER.info("Attachment.%s = <method>", attr)
                            else:
                                LOGGER.info("Attachment.%s = %s", attr, repr(value)[:200])
                        except Exception as e:
                            LOGGER.info("Attachment.%s = <error: %s>", attr, e)
                
                # Try different ways to get content type
                content_type = None
                if hasattr(attachment, 'content_type'):
                    content_type = attachment.content_type
                elif hasattr(attachment, 'mime_type'):
                    content_type = attachment.mime_type
                elif hasattr(attachment, 'type'):
                    content_type = attachment.type
                else:
                    # Try to guess from filename if available
                    if hasattr(attachment, 'filename'):
                        filename = attachment.filename.lower()
                        if filename.endswith(('.jpg', '.jpeg')):
                            content_type = 'image/jpeg'
                        elif filename.endswith('.png'):
                            content_type = 'image/png'
                        elif filename.endswith('.webp'):
                            content_type = 'image/webp'
                        elif filename.endswith('.gif'):
                            content_type = 'image/gif'
                    # Default to image/jpeg if we can't determine
                    if not content_type:
                        content_type = 'image/jpeg'
                        LOGGER.warning("Could not determine content type, defaulting to: %s", content_type)
                
                LOGGER.info("Processing attachment with content type: %s", content_type)
                
                if content_type and content_type.startswith("image/"):
                    try:
                        # Get the content data - try many different attributes
                        image_content = None
                        content_source = None
                        
                        # List of possible content attributes
                        content_attrs = ['content', 'data', 'binary_data', 'bytes', 'file_content', 'image_data', 'payload']
                        
                        for attr in content_attrs:
                            if hasattr(attachment, attr):
                                image_content = getattr(attachment, attr)
                                if image_content:  # Check if not None/empty
                                    content_source = attr
                                    LOGGER.info("Found image content via attachment.%s", attr)
                                    break
                        
                        # If still no content, try to read from file path/url
                        if not image_content:
                            if hasattr(attachment, 'file_path') and attachment.file_path:
                                try:
                                    with open(attachment.file_path, 'rb') as f:
                                        image_content = f.read()
                                        content_source = 'file_path'
                                        LOGGER.info("Loaded image content from file: %s", attachment.file_path)
                                except Exception as e:
                                    LOGGER.error("Failed to read file %s: %s", attachment.file_path, e)
                            elif hasattr(attachment, 'path') and attachment.path:
                                try:
                                    with open(attachment.path, 'rb') as f:
                                        image_content = f.read()
                                        content_source = 'path'
                                        LOGGER.info("Loaded image content from path: %s", attachment.path)
                                except Exception as e:
                                    LOGGER.error("Failed to read path %s: %s", attachment.path, e)
                            elif hasattr(attachment, 'url'):
                                LOGGER.warning("Attachment has URL but no direct content: %s", attachment.url)
                        
                        if not image_content:
                            LOGGER.error("Could not find image content in attachment after trying all methods")
                            LOGGER.error("Available attributes: %s", [attr for attr in dir(attachment) if not attr.startswith('_')])
                            continue
                        
                        LOGGER.info("Using image content from: %s (size: %d bytes)", content_source, len(image_content) if isinstance(image_content, bytes) else len(str(image_content)))
                            
                        # Convert image attachment to base64 URL format
                        if isinstance(image_content, bytes):
                            image_data = base64.b64encode(image_content).decode('utf-8')
                        else:
                            # Assume it's already base64 if string
                            image_data = image_content.replace('data:', '').split(',')[-1] if 'data:' in str(image_content) else str(image_content)
                        
                        message_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{image_data}",
                                "detail": "high"  # Use high detail for better analysis
                            }
                        })
                        LOGGER.info("Successfully added image attachment to message: %s", content_type)
                    except Exception as e:
                        LOGGER.error("Failed to process image attachment: %s", e)
                        # Add error message to chat instead
                        message_parts.append({
                            "type": "text",
                            "text": f"[Error: Could not process image attachment - {e}]"
                        })
            
            if message_parts:
                return ChatCompletionUserMessageParam(role="user", content=message_parts)
        
        # Fallback to simple text message
        if content.content:
            return ChatCompletionUserMessageParam(role="user", content=content.content)

    if role == "assistant":
        param = ChatCompletionAssistantMessageParam(
            role="assistant",
            content=content.content,
        )
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            tool_calls = []
            for tool_call in content.tool_calls:
                try:
                    # Try new OpenAI format first
                    tool_calls.append(ChatCompletionMessageFunctionToolCallParam(
                        type="function",
                        id=tool_call.id,
                        function=Function(
                            arguments=json.dumps(tool_call.tool_args),
                            name=tool_call.tool_name,
                        ),
                    ))
                except (TypeError, AttributeError):
                    # Fallback to dict format for older versions
                    tool_calls.append({
                        "type": "function",
                        "id": tool_call.id,
                        "function": {
                            "arguments": json.dumps(tool_call.tool_args),
                            "name": tool_call.tool_name,
                        },
                    })
            param["tool_calls"] = tool_calls
        return param
    LOGGER.warning("Could not convert message to Completions API: %s", content)
    return None


def _decode_tool_arguments(arguments: str) -> Any:
    """Decode tool call arguments."""
    try:
        return json.loads(arguments)
    except json.JSONDecodeError as err:
        raise HomeAssistantError(f"Unexpected tool argument response: {err}") from err


async def _transform_response(
    message: ChatCompletionMessage,
) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
    """Transform the OpenRouter message to a ChatLog format."""
    data: conversation.AssistantContentDeltaDict = {
        "role": message.role,
        "content": message.content,
    }
    if message.tool_calls:
        data["tool_calls"] = [
            llm.ToolInput(
                id=tool_call.id,
                tool_name=tool_call.function.name,
                tool_args=_decode_tool_arguments(tool_call.function.arguments),
            )
            for tool_call in message.tool_calls
            if tool_call.type == "function"
        ]
    yield data


class OpenRouterEntity(Entity):
    """Base entity for Open Router."""

    _attr_has_entity_name = True

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self.model = subentry.data[CONF_MODEL]
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log."""

        model_args = {
            "model": self.model,
            "user": chat_log.conversation_id,
            "extra_headers": {
                "X-Title": "Home Assistant",
                "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
            },
            "extra_body": {"require_parameters": True},
        }

        tools: list[ChatCompletionFunctionToolParam] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        if tools:
            model_args["tools"] = tools

        model_args["messages"] = [
            m
            for content in chat_log.content
            if (m := _convert_content_to_chat_message(content))
        ]

        if structure:
            if TYPE_CHECKING:
                assert structure_name is not None
            # Create response format compatible with both old and new OpenAI versions
            json_schema = _format_structured_output(
                structure_name, structure, chat_log.llm_api
            )
            try:
                # Try new OpenAI format first
                model_args["response_format"] = ResponseFormatJSONSchema(
                    type="json_schema",
                    json_schema=json_schema,
                )
            except (TypeError, AttributeError):
                # Fallback to dict format for compatibility
                model_args["response_format"] = {
                    "type": "json_schema",
                    "json_schema": json_schema,
                }

        client = self.entry.runtime_data

        # Check if we're sending images to a non-vision model
        has_images = any(
            isinstance(msg.get("content"), list) and 
            any(part.get("type") == "image_url" for part in msg.get("content", []))
            for msg in model_args.get("messages", [])
        )
        
        if has_images:
            LOGGER.info("Sending image content to model: %s", self.model)
            
        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                result = await client.chat.completions.create(**model_args)
            except openai.BadRequestError as err:
                if "vision" in str(err).lower() or "image" in str(err).lower():
                    LOGGER.error("Model %s does not support vision/images. Please use a vision-capable model like gpt-4-vision-preview, claude-3-haiku, etc.", self.model)
                    raise HomeAssistantError(f"Model {self.model} does not support images. Please configure a vision-capable model.") from err
                LOGGER.error("Bad request to API: %s", err)
                raise HomeAssistantError("Bad request to API") from err
            except openai.OpenAIError as err:
                LOGGER.error("Error talking to API: %s", err)
                raise HomeAssistantError("Error talking to API") from err

            result_message = result.choices[0].message

            model_args["messages"].extend(
                [
                    msg
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id, _transform_response(result_message)
                    )
                    if (msg := _convert_content_to_chat_message(content))
                ]
            )
            if not chat_log.unresponded_tool_results:
                break
