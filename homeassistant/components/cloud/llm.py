"""Helpers for cloud LLM chat handling."""

import base64
from collections.abc import Callable
import io
from typing import Any, cast

from hass_nabucasa.llm import LLMImageAttachment
from openai.types.responses import FunctionToolParam, ToolParam, WebSearchToolParam
from PIL import Image
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm


class LLMChatHelper:
    """Helper methods for LLM chat handling."""

    @staticmethod
    async def prepare_chat_for_generation(
        hass: HomeAssistant,
        chat_log: conversation.ChatLog,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Prepare kwargs for Cloud LLM from the chat log."""

        messages = [
            message
            for content in chat_log.content
            if (message := LLMChatHelper._convert_content_to_chat_message(content))
        ]

        if not messages or messages[-1]["role"] != "user":
            raise HomeAssistantError("No user prompt found")

        last_content = chat_log.content[-1]
        if last_content.role == "user" and last_content.attachments:
            files = await LLMChatHelper.async_prepare_files_for_prompt(
                hass, last_content.attachments
            )
            user_message = messages[-1]
            current_content = user_message.get("content", [])
            user_message["content"] = [*(current_content or []), *files]

        tools: list[ToolParam] = []
        tool_choice: str | None = None

        if chat_log.llm_api:
            ha_tools: list[ToolParam] = [
                LLMChatHelper._format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

            if ha_tools:
                if not chat_log.unresponded_tool_results:
                    tools = ha_tools
                    tool_choice = "auto"
                else:
                    tools = []
                    tool_choice = "none"

        web_search = WebSearchToolParam(
            type="web_search",
            search_context_size="medium",
        )
        tools.append(web_search)

        response_kwargs: dict[str, Any] = {
            "messages": messages,
            "conversation_id": chat_log.conversation_id,
        }

        if response_format is not None:
            response_kwargs["response_format"] = response_format
        if tools is not None:
            response_kwargs["tools"] = tools
        if tool_choice is not None:
            response_kwargs["tool_choice"] = tool_choice

        return response_kwargs

    @staticmethod
    def _convert_content_to_chat_message(
        content: conversation.Content,
    ) -> dict[str, Any] | None:
        """Convert ChatLog content to a responses message."""
        if content.role not in ("user", "system", "tool_result", "assistant"):
            return None

        text_content = cast(
            conversation.SystemContent
            | conversation.UserContent
            | conversation.AssistantContent,
            content,
        )

        if not text_content.content:
            return None

        content_type = (
            "output_text" if text_content.role == "assistant" else "input_text"
        )

        return {
            "role": text_content.role,
            "content": [
                {
                    "type": content_type,
                    "text": text_content.content,
                }
            ],
        }

    @staticmethod
    async def async_prepare_files_for_prompt(
        hass: HomeAssistant, attachments: list[conversation.Attachment]
    ) -> list[dict[str, Any]]:
        """Prepare files for multimodal prompts."""

        def prepare() -> list[dict[str, Any]]:
            content: list[dict[str, Any]] = []
            for attachment in attachments:
                mime_type = attachment.mime_type
                path = attachment.path
                if not path.exists():
                    raise HomeAssistantError(f"`{path}` does not exist")

                data = base64.b64encode(path.read_bytes()).decode("utf-8")
                if mime_type and mime_type.startswith("image/"):
                    content.append(
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{data}",
                        }
                    )
                elif mime_type and mime_type.startswith("application/pdf"):
                    content.append(
                        {
                            "type": "input_text",
                            "text": f"[File: {path.name}]\nContent: {data}",
                        }
                    )
                else:
                    raise HomeAssistantError(
                        "Only images and PDF are currently supported as attachments"
                    )

            return content

        return await hass.async_add_executor_job(prepare)

    @staticmethod
    def _format_tool(
        tool: llm.Tool,
        custom_serializer: Callable[[Any], Any] | None,
    ) -> ToolParam:
        """Format a Home Assistant tool for the OpenAI Responses API."""
        parameters = convert(tool.parameters, custom_serializer=custom_serializer)

        spec: FunctionToolParam = {
            "type": "function",
            "name": tool.name,
            "strict": False,
            "description": tool.description,
            "parameters": parameters,
        }

        return spec


class LLMFileHelper:
    """Helper methods for LLM file handling."""

    @staticmethod
    def _convert_image_for_editing(data: bytes) -> tuple[bytes, str]:
        """Ensure the image data is in a format accepted by OpenAI image edits."""
        stream = io.BytesIO(data)
        with Image.open(stream) as img:
            mode = img.mode
            if mode not in ("RGBA", "LA", "L"):
                img = img.convert("RGBA")

            output = io.BytesIO()
            if img.mode in ("RGBA", "LA", "L"):
                img.save(output, format="PNG")
                return output.getvalue(), "image/png"

            img.save(output, format=img.format or "PNG")
            return output.getvalue(), f"image/{(img.format or 'png').lower()}"

    @staticmethod
    async def async_prepare_image_generation_attachments(
        hass: HomeAssistant, attachments: list[conversation.Attachment]
    ) -> list[LLMImageAttachment]:
        """Load attachment data for image generation."""

        def prepare() -> list[LLMImageAttachment]:
            items: list[LLMImageAttachment] = []
            for attachment in attachments:
                if not attachment.mime_type or not attachment.mime_type.startswith(
                    "image/"
                ):
                    raise HomeAssistantError(
                        "Only image attachments are supported for image generation"
                    )
                path = attachment.path
                if not path.exists():
                    raise HomeAssistantError(f"`{path}` does not exist")

                data = path.read_bytes()
                mime_type = attachment.mime_type

                try:
                    data, mime_type = LLMFileHelper._convert_image_for_editing(data)
                except HomeAssistantError:
                    raise
                except Exception as err:
                    raise HomeAssistantError(
                        "Failed to process image attachment"
                    ) from err

                items.append(
                    LLMImageAttachment(
                        filename=path.name,
                        mime_type=mime_type,
                        data=data,
                    )
                )

            return items

        return await hass.async_add_executor_job(prepare)
