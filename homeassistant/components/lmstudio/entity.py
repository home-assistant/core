"""Base entity for the LM Studio integration."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator
import json
import logging
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Final

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from . import LMStudioConfigEntry
from .client import LMStudioAuthError, LMStudioConnectionError, LMStudioResponseError
from .const import (
    CONF_CONTEXT_LENGTH,
    CONF_MAX_HISTORY,
    CONF_MAX_OUTPUT_TOKENS,
    CONF_MIN_P,
    CONF_MODEL,
    CONF_REASONING,
    CONF_REPEAT_PENALTY,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_MAX_HISTORY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_HISTORY_SEPARATOR: Final = "\n"


class LMStudioBaseLLMEntity(Entity):
    """LM Studio base LLM entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_available = True

    def __init__(self, entry: LMStudioConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._model = subentry.data[CONF_MODEL]
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="LM Studio",
            model=self._model,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log."""
        settings = {**self.entry.data, **self.subentry.data}
        system_prompt = self._get_system_prompt(chat_log)
        prompt_signature = self._normalize_system_prompt(system_prompt)

        if structure:
            system_prompt = self._add_structure_prompt(
                system_prompt, structure, chat_log.llm_api
            )

        previous_response_id = (
            self.entry.runtime_data.conversation_store.get_previous_response_id(
                chat_log.conversation_id, self._model, prompt_signature
            )
        )

        history_text = ""
        if previous_response_id is None:
            max_history = int(settings.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY))
            history_text = self._format_history(chat_log, max_history)

        user_content = self._get_latest_user_content(chat_log)
        user_text = user_content.content or ""

        input_text = self._build_input_text(history_text, user_text)
        input_payload = await self._async_build_input_payload(
            input_text, user_content.attachments
        )

        payload: dict[str, Any] = {
            "model": self._model,
            "input": input_payload,
            "system_prompt": system_prompt,
            "stream": True,
            "store": True,
        }

        if previous_response_id is not None:
            payload["previous_response_id"] = previous_response_id

        self._add_optional_params(payload, settings)

        try:
            async for _ in chat_log.async_add_delta_content_stream(
                self.entity_id,
                self._async_stream_response(chat_log, payload, prompt_signature),
            ):
                pass
        except LMStudioAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except LMStudioConnectionError as err:
            self._handle_unavailable(err)
            _LOGGER.error("Unexpected error talking to server: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        except LMStudioResponseError as err:
            _LOGGER.error("Unexpected error talking to server: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err
        else:
            self._handle_recovered()

    @staticmethod
    def _get_system_prompt(chat_log: conversation.ChatLog) -> str:
        """Return the system prompt from the chat log."""
        if not chat_log.content:
            return ""
        first = chat_log.content[0]
        if isinstance(first, conversation.SystemContent) and first.content:
            return first.content
        return ""

    def _handle_unavailable(self, err: Exception) -> None:
        """Log and mark the server as unavailable."""
        if not self.entry.runtime_data.unavailable_logged:
            _LOGGER.info("The server is unavailable: %s", err)
            self.entry.runtime_data.unavailable_logged = True
        if self._attr_available:
            self._attr_available = False
            self.async_write_ha_state()

    def _handle_recovered(self) -> None:
        """Log and mark the server as recovered."""
        if self.entry.runtime_data.unavailable_logged:
            _LOGGER.info("The server is back online")
            self.entry.runtime_data.unavailable_logged = False
        if not self._attr_available:
            self._attr_available = True
            self.async_write_ha_state()

    @staticmethod
    def _normalize_system_prompt(system_prompt: str) -> str:
        """Normalize system prompt for conversation state tracking."""
        lines = [
            line
            for line in system_prompt.splitlines()
            if not line.startswith("Current time is ")
        ]
        return "\n".join(lines).strip()

    @staticmethod
    def _build_input_text(history_text: str, user_text: str) -> str:
        """Build input text for the request."""
        if history_text:
            return f"Conversation so far:{_HISTORY_SEPARATOR}{history_text}\n\nUser: {user_text}"
        return user_text

    def _format_history(self, chat_log: conversation.ChatLog, max_history: int) -> str:
        """Format chat history for the request."""
        if max_history < 1:
            return ""

        rounds: list[list[conversation.Content]] = []
        current_round: list[conversation.Content] = []

        for content in chat_log.content[1:-1]:
            if content.role == "user":
                if current_round:
                    rounds.append(current_round)
                current_round = [content]
                continue

            if current_round:
                current_round.append(content)

        if current_round:
            rounds.append(current_round)

        history_lines: list[str] = []

        for round_content in rounds[-max_history:]:
            for content in round_content:
                if content.role == "user":
                    history_lines.append(f"User: {content.content or ''}")
                elif content.role == "assistant":
                    history_lines.append(f"Assistant: {content.content or ''}")
                elif content.role == "tool_result":
                    history_lines.append(
                        f"Tool result ({content.tool_name}): {content.tool_result}"
                    )
                else:
                    history_lines.append(f"{content.role}: {content.content or ''}")

        return _HISTORY_SEPARATOR.join(history_lines)

    @staticmethod
    def _add_structure_prompt(
        system_prompt: str,
        structure: vol.Schema,
        llm_api: llm.APIInstance | None,
    ) -> str:
        """Append structured output guidance to the system prompt."""
        schema = convert(
            structure,
            custom_serializer=(
                llm_api.custom_serializer if llm_api else llm.selector_serializer
            ),
        )
        schema_text = json.dumps(schema, ensure_ascii=True)
        guidance = (
            "Return only valid JSON that matches this schema. Do not add extra keys."
            f"\nJSON schema: {schema_text}"
        )
        if system_prompt:
            return f"{system_prompt}\n\n{guidance}"
        return guidance

    @staticmethod
    def _get_latest_user_content(
        chat_log: conversation.ChatLog,
    ) -> conversation.UserContent:
        """Return the latest user content in the log."""
        for content in reversed(chat_log.content):
            if isinstance(content, conversation.UserContent):
                return content
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_user_content",
        )

    async def _async_build_input_payload(
        self,
        input_text: str,
        attachments: list[conversation.Attachment] | None,
    ) -> str | list[dict[str, Any]]:
        """Build the input payload for LM Studio."""
        if not attachments:
            return input_text

        inputs: list[dict[str, Any]] = [
            {
                "type": "message",
                "content": input_text,
            }
        ]

        images = await self._async_encode_attachments(attachments)
        inputs.extend(images)
        return inputs

    async def _async_encode_attachments(
        self, attachments: list[conversation.Attachment]
    ) -> list[dict[str, Any]]:
        """Encode image attachments for LM Studio."""
        encode_targets: list[tuple[str, str]] = []

        for attachment in attachments:
            mime_type = attachment.mime_type
            file_path = str(attachment.path)
            if mime_type is None:
                mime_type = guess_type(file_path)[0]

            if not mime_type or not mime_type.startswith("image/"):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unsupported_attachment_type",
                )

            encode_targets.append((file_path, mime_type))

        encoded_urls = await asyncio.gather(
            *[
                self._async_encode_image(file_path, mime_type)
                for file_path, mime_type in encode_targets
            ]
        )

        return [{"type": "image", "data_url": data_url} for data_url in encoded_urls]

    async def _async_encode_image(self, file_path: str, mime_type: str) -> str:
        """Encode an image attachment to a data URL."""
        path = Path(file_path)

        def _read_file() -> bytes:
            if not path.exists():
                raise FileNotFoundError(path)
            return path.read_bytes()

        try:
            data = await self.hass.async_add_executor_job(_read_file)
        except FileNotFoundError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="attachment_not_found",
                translation_placeholders={"file_path": file_path},
            ) from err

        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _add_optional_params(
        self, payload: dict[str, Any], settings: dict[str, Any]
    ) -> None:
        """Add optional parameters to the payload."""
        if (max_output_tokens := settings.get(CONF_MAX_OUTPUT_TOKENS)) is not None:
            payload["max_output_tokens"] = int(max_output_tokens)
        if (temperature := settings.get(CONF_TEMPERATURE)) is not None:
            payload["temperature"] = float(temperature)
        if (top_p := settings.get(CONF_TOP_P)) is not None:
            payload["top_p"] = float(top_p)
        if (top_k := settings.get(CONF_TOP_K)) is not None:
            payload["top_k"] = int(top_k)
        if (min_p := settings.get(CONF_MIN_P)) is not None:
            payload["min_p"] = float(min_p)
        if (repeat_penalty := settings.get(CONF_REPEAT_PENALTY)) is not None:
            payload["repeat_penalty"] = float(repeat_penalty)
        if (context_length := settings.get(CONF_CONTEXT_LENGTH)) is not None:
            payload["context_length"] = int(context_length)
        if (reasoning := settings.get(CONF_REASONING)) not in (None, "off"):
            payload["reasoning"] = reasoning

    async def _async_stream_response(
        self,
        chat_log: conversation.ChatLog,
        payload: dict[str, Any],
        prompt_signature: str,
    ) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
        """Stream LM Studio response to the chat log."""
        new_message = True
        stream_error: str | None = None

        async for event in self.entry.runtime_data.client.async_stream_chat(payload):
            name = event.name
            data = event.data

            if name == "message.start":
                new_message = True
                continue

            if name == "message.delta":
                content = data.get("content")
                if not isinstance(content, str):
                    continue

                delta: conversation.AssistantContentDeltaDict = {"content": content}
                if new_message:
                    delta["role"] = "assistant"
                    new_message = False

                yield delta
                continue

            if name == "reasoning.delta":
                reasoning_content = data.get("content")
                if isinstance(reasoning_content, str):
                    yield {"thinking_content": reasoning_content}
                continue

            if name == "message.end":
                new_message = True
                continue

            if name == "error":
                message = data.get("message")
                if isinstance(message, str):
                    stream_error = message
                continue

            if name == "chat.end":
                response_id = data.get("response_id")
                if isinstance(response_id, str):
                    self.entry.runtime_data.conversation_store.set_response_id(
                        chat_log.conversation_id,
                        self._model,
                        prompt_signature,
                        response_id,
                    )
                if stats := data.get("stats"):
                    chat_log.async_trace({"stats": stats})
                continue

        if stream_error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="stream_error",
                translation_placeholders={"message": stream_error},
            )
