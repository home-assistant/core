"""The Google Generative AI Conversation integration."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from google.ai import generativelanguage_v1beta
from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import ClientError, DeadlineExceeded, GoogleAPIError
import google.generativeai as genai
import google.generativeai.types as genai_types
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
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CHAT_MODEL, CONF_PROMPT, DOMAIN, RECOMMENDED_CHAT_MODEL

SERVICE_GENERATE_CONTENT = "generate_content"
CONF_IMAGE_FILENAME = "image_filename"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (Platform.CONVERSATION,)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Generative AI Conversation."""

    async def generate_content(call: ServiceCall) -> ServiceResponse:
        """Generate content from text and optionally images."""
        prompt_parts = [call.data[CONF_PROMPT]]
        image_filenames = call.data[CONF_IMAGE_FILENAME]
        for image_filename in image_filenames:
            if not hass.config.is_allowed_path(image_filename):
                raise HomeAssistantError(
                    f"Cannot read `{image_filename}`, no access to path; "
                    "`allowlist_external_dirs` may need to be adjusted in "
                    "`configuration.yaml`"
                )
            if not Path(image_filename).exists():
                raise HomeAssistantError(f"`{image_filename}` does not exist")
            mime_type, _ = mimetypes.guess_type(image_filename)
            if mime_type is None or not mime_type.startswith("image"):
                raise HomeAssistantError(f"`{image_filename}` is not an image")
            prompt_parts.append(
                {
                    "mime_type": mime_type,
                    "data": await hass.async_add_executor_job(
                        Path(image_filename).read_bytes
                    ),
                }
            )

        model = genai.GenerativeModel(model_name=RECOMMENDED_CHAT_MODEL)

        try:
            response = await model.generate_content_async(prompt_parts)
        except (
            GoogleAPIError,
            ValueError,
            genai_types.BlockedPromptException,
            genai_types.StopCandidateException,
        ) as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err

        if not response.parts:
            raise HomeAssistantError("Error generating content")

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
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Generative AI Conversation from a config entry."""
    genai.configure(api_key=entry.data[CONF_API_KEY])

    try:
        client = generativelanguage_v1beta.ModelServiceAsyncClient(
            client_options=ClientOptions(api_key=entry.data[CONF_API_KEY])
        )
        await client.get_model(
            name=entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL), timeout=5.0
        )
    except (GoogleAPIError, ValueError) as err:
        if isinstance(err, ClientError) and err.reason == "API_KEY_INVALID":
            raise ConfigEntryAuthFailed(err) from err
        if isinstance(err, DeadlineExceeded):
            raise ConfigEntryNotReady(err) from err
        raise ConfigEntryError(err) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload GoogleGenerativeAI."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    return True
