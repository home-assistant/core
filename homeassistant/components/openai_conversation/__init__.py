"""The OpenAI Conversation integration."""

from __future__ import annotations

import base64
from mimetypes import guess_file_type
from pathlib import Path

import openai
from openai.types.images_response import ImagesResponse
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseInputFileParam,
    ResponseInputImageParam,
    ResponseInputMessageContentListParam,
    ResponseInputParam,
    ResponseInputTextParam,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHAT_MODEL,
    CONF_FILENAMES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

SERVICE_GENERATE_IMAGE = "generate_image"
SERVICE_GENERATE_CONTENT = "generate_content"

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type OpenAIConfigEntry = ConfigEntry[openai.AsyncClient]


def encode_file(file_path: str) -> tuple[str, str]:
    """Return base64 version of file contents."""
    mime_type, _ = guess_file_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    with open(file_path, "rb") as image_file:
        return (mime_type, base64.b64encode(image_file.read()).decode("utf-8"))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up OpenAI Conversation."""
    await async_migrate_integration(hass)

    async def render_image(call: ServiceCall) -> ServiceResponse:
        """Render an image with dall-e."""
        entry_id = call.data["config_entry"]
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": entry_id},
            )

        client: openai.AsyncClient = entry.runtime_data

        try:
            response: ImagesResponse = await client.images.generate(
                model="dall-e-3",
                prompt=call.data[CONF_PROMPT],
                size=call.data["size"],
                quality=call.data["quality"],
                style=call.data["style"],
                response_format="url",
                n=1,
            )
        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error generating image: {err}") from err

        if not response.data or not response.data[0].url:
            raise HomeAssistantError("No image returned")

        return response.data[0].model_dump(exclude={"b64_json"})

    async def send_prompt(call: ServiceCall) -> ServiceResponse:
        """Send a prompt to ChatGPT and return the response."""
        entry_id = call.data["config_entry"]
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry": entry_id},
            )

        # Get first conversation subentry for options
        conversation_subentry = next(
            (
                sub
                for sub in entry.subentries.values()
                if sub.subentry_type == "conversation"
            ),
            None,
        )
        if not conversation_subentry:
            raise ServiceValidationError("No conversation configuration found")

        model: str = conversation_subentry.data.get(
            CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL
        )
        client: openai.AsyncClient = entry.runtime_data

        content: ResponseInputMessageContentListParam = [
            ResponseInputTextParam(type="input_text", text=call.data[CONF_PROMPT])
        ]

        def append_files_to_content() -> None:
            for filename in call.data[CONF_FILENAMES]:
                if not hass.config.is_allowed_path(filename):
                    raise HomeAssistantError(
                        f"Cannot read `{filename}`, no access to path; "
                        "`allowlist_external_dirs` may need to be adjusted in "
                        "`configuration.yaml`"
                    )
                if not Path(filename).exists():
                    raise HomeAssistantError(f"`{filename}` does not exist")
                mime_type, base64_file = encode_file(filename)
                if "image/" in mime_type:
                    content.append(
                        ResponseInputImageParam(
                            type="input_image",
                            image_url=f"data:{mime_type};base64,{base64_file}",
                            detail="auto",
                        )
                    )
                elif "application/pdf" in mime_type:
                    content.append(
                        ResponseInputFileParam(
                            type="input_file",
                            filename=filename,
                            file_data=f"data:{mime_type};base64,{base64_file}",
                        )
                    )
                else:
                    raise HomeAssistantError(
                        "Only images and PDF are supported by the OpenAI API,"
                        f"`{filename}` is not an image file or PDF"
                    )

        if CONF_FILENAMES in call.data:
            await hass.async_add_executor_job(append_files_to_content)

        messages: ResponseInputParam = [
            EasyInputMessageParam(type="message", role="user", content=content)
        ]

        try:
            model_args = {
                "model": model,
                "input": messages,
                "max_output_tokens": conversation_subentry.data.get(
                    CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
                ),
                "top_p": conversation_subentry.data.get(CONF_TOP_P, RECOMMENDED_TOP_P),
                "temperature": conversation_subentry.data.get(
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                ),
                "user": call.context.user_id,
                "store": False,
            }

            if model.startswith("o"):
                model_args["reasoning"] = {
                    "effort": conversation_subentry.data.get(
                        CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT
                    )
                }

            response: Response = await client.responses.create(**model_args)

        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err
        except FileNotFoundError as err:
            raise HomeAssistantError(f"Error generating content: {err}") from err

        return {"text": response.output_text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        send_prompt,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional(CONF_FILENAMES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        render_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional("size", default="1024x1024"): vol.In(
                    ("1024x1024", "1024x1792", "1792x1024")
                ),
                vol.Optional("quality", default="standard"): vol.In(("standard", "hd")),
                vol.Optional("style", default="vivid"): vol.In(("vivid", "natural")),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenAIConfigEntry) -> bool:
    """Set up OpenAI Conversation from a config entry."""
    client = openai.AsyncOpenAI(
        api_key=entry.data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )

    # Cache current platform data which gets added to each request (caching done by library)
    _ = await hass.async_add_executor_job(client.platform_headers)

    try:
        await hass.async_add_executor_job(client.with_options(timeout=10.0).models.list)
    except openai.AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        return False
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure."""

    entries = hass.config_entries.async_entries(DOMAIN)
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, ConfigEntry] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        use_existing = False
        subentry = ConfigSubentry(
            data=entry.options,
            subentry_type="conversation",
            title=entry.title,
            unique_id=None,
        )
        if entry.data[CONF_API_KEY] not in api_keys_entries:
            use_existing = True
            api_keys_entries[entry.data[CONF_API_KEY]] = entry

        parent_entry = api_keys_entries[entry.data[CONF_API_KEY]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)
        conversation_entity = entity_registry.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        if conversation_entity is not None:
            entity_registry.async_update_entity(
                conversation_entity,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                new_unique_id=subentry.subentry_id,
            )

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                new_identifiers={(DOMAIN, subentry.subentry_id)},
                add_config_subentry_id=subentry.subentry_id,
                add_config_entry_id=parent_entry.entry_id,
            )
            if parent_entry.entry_id != entry.entry_id:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                )
            else:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                    remove_config_subentry_id=None,
                )

        if not use_existing:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_NAME,
                options={},
                version=2,
                minor_version=2,
            )


async def async_migrate_entry(hass: HomeAssistant, entry: OpenAIConfigEntry) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 2 and entry.minor_version == 1:
        # Correct broken device migration in Home Assistant Core 2025.7.0b0-2025.7.0b1
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            device_registry.async_update_device(
                device.id,
                remove_config_entry_id=entry.entry_id,
                remove_config_subentry_id=None,
            )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True
