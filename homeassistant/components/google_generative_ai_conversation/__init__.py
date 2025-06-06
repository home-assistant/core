"""The Google Generative AI Conversation integration."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from google.genai import Client
from google.genai.errors import APIError, ClientError
from google.genai.types import (
    File,
    FileState,
    GenerateContentConfig,
    HarmCategory,
    SafetySetting,
)
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
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_TOP_K,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    DOMAIN,
    FILE_POLLING_INTERVAL_SECONDS,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TOP_K,
    TIMEOUT_MILLIS,
)

SERVICE_GENERATE_CONTENT = "generate_content"
CONF_IMAGE_FILENAME = "image_filename"
CONF_FILENAMES = "filenames"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)

type GoogleGenerativeAIConfigEntry = ConfigEntry[Client]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Generative AI Conversation."""

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
        options = config_entry.options

        def append_files_to_prompt():
            image_filenames = call.data[CONF_IMAGE_FILENAME]
            filenames = call.data[CONF_FILENAMES]
            for filename in set(image_filenames + filenames):
                if not hass.config.is_allowed_path(filename):
                    raise HomeAssistantError(
                        f"Cannot read `{filename}`, no access to path; "
                        "`allowlist_external_dirs` may need to be adjusted in "
                        "`configuration.yaml`"
                    )
                if not Path(filename).exists():
                    raise HomeAssistantError(f"`{filename}` does not exist")
                mimetype = mimetypes.guess_type(filename)[0]
                with open(filename, "rb") as file:
                    uploaded_file = client.files.upload(
                        file=file, config={"mime_type": mimetype}
                    )
                    prompt_parts.append(uploaded_file)

        async def wait_for_file_processing(uploaded_file: File) -> None:
            """Wait for file processing to complete."""
            while True:
                uploaded_file = await client.aio.files.get(
                    name=uploaded_file.name,
                    config={"http_options": {"timeout": TIMEOUT_MILLIS}},
                )
                if uploaded_file.state not in (
                    FileState.STATE_UNSPECIFIED,
                    FileState.PROCESSING,
                ):
                    break
                LOGGER.debug(
                    "Waiting for file `%s` to be processed, current state: %s",
                    uploaded_file.name,
                    uploaded_file.state,
                )
                await asyncio.sleep(FILE_POLLING_INTERVAL_SECONDS)

            if uploaded_file.state == FileState.FAILED:
                raise HomeAssistantError(
                    f"File `{uploaded_file.name}` processing failed, reason: {uploaded_file.error.message}"
                )

        await hass.async_add_executor_job(append_files_to_prompt)

        tasks = [
            asyncio.create_task(wait_for_file_processing(part))
            for part in prompt_parts
            if isinstance(part, File) and part.state != FileState.ACTIVE
        ]
        async with asyncio.timeout(TIMEOUT_MILLIS / 1000):
            await asyncio.gather(*tasks)

        generate_content_config = GenerateContentConfig(
            temperature=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
            top_k=options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
            top_p=options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            max_output_tokens=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            safety_settings=[
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=options.get(
                        CONF_HARASSMENT_BLOCK_THRESHOLD,
                        RECOMMENDED_HARM_BLOCK_THRESHOLD,
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=options.get(
                        CONF_HATE_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=options.get(
                        CONF_SEXUAL_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=options.get(
                        CONF_DANGEROUS_BLOCK_THRESHOLD, RECOMMENDED_HARM_BLOCK_THRESHOLD
                    ),
                ),
            ],
        )

        chat_model = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        try:
            response = await client.aio.models.generate_content(
                model=chat_model,
                contents=prompt_parts,
                config=generate_content_config,
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

        if not response.candidates[0].content.parts:
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
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Set up Google Generative AI Conversation from a config entry."""

    try:

        def _init_client() -> Client:
            return Client(api_key=entry.data[CONF_API_KEY])

        client = await hass.async_add_executor_job(_init_client)
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
