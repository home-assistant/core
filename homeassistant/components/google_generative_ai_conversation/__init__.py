"""The Google Generative AI Conversation integration."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from google.genai import Client
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
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    TIMEOUT_MILLIS,
)
from .model_setup import get_content_config

SERVICE_GENERATE_CONTENT = "generate_content"
CONF_IMAGE_FILENAME = "image_filename"
CONF_FILENAMES = "filenames"
CONF_CONFIG_ENTRY = "config_entry"

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

        config_entry: GoogleGenerativeAIConfigEntry
        if CONF_CONFIG_ENTRY in call.data:
            entry_id = call.data[CONF_CONFIG_ENTRY]
            found_entry = hass.config_entries.async_get_entry(entry_id)
            if found_entry is None or found_entry.domain != DOMAIN:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_config_entry",
                    translation_placeholders={"config_entry": entry_id},
                )
            config_entry = found_entry
        else:
            # Deprecated in 2025.6, to remove in 2025.10
            async_create_issue(
                hass,
                DOMAIN,
                "missing_config_entry_parameter",
                breaks_in_ha_version="2025.10.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="missing_config_entry_parameter",
            )
            config_entry = hass.config_entries.async_loaded_entries(DOMAIN)[0]

        prompt_parts = [call.data[CONF_PROMPT]]

        client = config_entry.runtime_data

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

        await hass.async_add_executor_job(append_files_to_prompt)

        model_name = config_entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)

        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                # Features like tools and custom prompts are powered by
                # HA's Conversation infra, so we cannot use them here.
                config=get_content_config(config_entry),
                contents=prompt_parts,
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
                vol.Optional(CONF_CONFIG_ENTRY): cv.string,
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
