"""The Google Generative AI Conversation integration."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import aiofiles
from google.genai import Client, types
from google.genai.errors import APIError, ClientError
from requests.exceptions import Timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_IMAGE_MODEL,
    TIMEOUT_MILLIS,
)

SERVICE_GENERATE_CONTENT = "generate_content"
SERVICE_GENERATE_IMAGE = "generate_image"
CONF_IMAGE_FILENAME = "image_filename"
CONF_FILENAMES = "filenames"
CONF_OUTPUT_FILENAME = "output_filename"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)

type GoogleGenerativeAIConfigEntry = ConfigEntry[Client]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Generative AI Conversation."""

    async def upload_attachments(
        client: Client, filenames: Iterable[str]
    ) -> list[types.File]:
        """Upload attachments and return a list of parts."""
        parts = []
        for filename in filenames:
            if not hass.config.is_allowed_path(filename):
                raise HomeAssistantError(
                    f"Cannot read `{filename}`, no access to path; "
                    "`allowlist_external_dirs` may need to be adjusted in "
                    "`configuration.yaml`"
                )
            if not Path(filename).exists():
                raise HomeAssistantError(f"`{filename}` does not exist")
            parts.append(await client.aio.files.upload(file=filename))
        return parts

    async def generate_content(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""

        if call.data[CONF_IMAGE_FILENAME]:
            # Deprecated in 2025.3, to remove in 2025.9
            async_create_issue(
                hass,
                DOMAIN,
                "deprecated_image_filename_parameter",
                breaks_in_ha_version="2025.9.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_image_filename_parameter",
            )

        prompt_parts = [call.data[CONF_PROMPT]]

        config_entry: GoogleGenerativeAIConfigEntry = (
            hass.config_entries.async_loaded_entries(DOMAIN)[0]
        )

        client = config_entry.runtime_data

        prompt_parts += await upload_attachments(
            client,
            set(call.data[CONF_IMAGE_FILENAME] + call.data[CONF_FILENAMES]),
        )

        try:
            response = await client.aio.models.generate_content(
                model=RECOMMENDED_CHAT_MODEL, contents=prompt_parts
            )
        except (
            APIError,
            ValueError,
        ) as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err

        if response.prompt_feedback:
            raise HomeAssistantError(
                f"Error generating content due to content violations, reason: {response.prompt_feedback.block_reason_message}"
            )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise HomeAssistantError("Unknown error generating content")

        return {"text": response.text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        generate_content,
        schema=vol.Schema(
            {
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional(CONF_IMAGE_FILENAME, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    async def generate_image(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""

        output_filename = call.data[CONF_OUTPUT_FILENAME]
        if not hass.config.is_allowed_path(output_filename):
            raise HomeAssistantError(
                f"Cannot save to `{output_filename}`, no access to path; "
                "`allowlist_external_dirs` may need to be adjusted in "
                "`configuration.yaml`"
            )

        prompt_parts = [call.data[CONF_PROMPT]]

        config_entry: GoogleGenerativeAIConfigEntry = (
            hass.config_entries.async_loaded_entries(DOMAIN)[0]
        )

        client = config_entry.runtime_data

        prompt_parts += await upload_attachments(
            client,
            call.data[CONF_FILENAMES],
        )

        try:
            response = await client.aio.models.generate_content(
                model=RECOMMENDED_IMAGE_MODEL,
                contents=prompt_parts,
                config=types.GenerateContentConfig(
                    response_modalities=["Text", "Image"],
                ),
            )
        except (
            APIError,
            ValueError,
        ) as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err

        if response.prompt_feedback:
            raise HomeAssistantError(
                f"Error generating content due to content violations, reason: {response.prompt_feedback.block_reason_message}"
            )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise HomeAssistantError("Unknown error generating content")

        image_parts = [
            part
            for part in response.candidates[0].content.parts
            if part.inline_data
            and part.inline_data.mime_type
            and part.inline_data.mime_type.startswith("image/")
        ]
        if (
            len(image_parts) != 1
            or not image_parts[0].inline_data
            or not image_parts[0].inline_data.data
        ):
            raise HomeAssistantError(
                f"Prompt did not generate exactly one image; found {len(image_parts)} images.\n\nResponse text: {response.text}"
            )

        async with aiofiles.open(output_filename, "wb") as file:
            await file.write(image_parts[0].inline_data.data)

        return {"text": response.text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        generate_image,
        schema=vol.Schema(
            {
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Required(CONF_OUTPUT_FILENAME): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Set up Google Generative AI Conversation from a config entry."""

    try:
        client = Client(api_key=entry.data[CONF_API_KEY])
        await client.aio.models.get(
            model=entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
            config={"http_options": {"timeout": TIMEOUT_MILLIS}},
        )
    except (APIError, Timeout) as err:
        if isinstance(err, ClientError) and "API_KEY_INVALID" in str(err):
            raise ConfigEntryAuthFailed(err.message) from err
        if isinstance(err, Timeout):
            raise ConfigEntryNotReady(err) from err
        raise ConfigEntryError(err) from err
    else:
        entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Unload GoogleGenerativeAI."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    return True
