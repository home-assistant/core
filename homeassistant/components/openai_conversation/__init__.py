"""The OpenAI Conversation integration."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from functools import partial
from io import BytesIO
from mimetypes import guess_file_type
from pathlib import Path

from aiohttp import web
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
from PIL import Image
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView
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
    issue_registry as ir,
    selector,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CHAT_MODEL,
    CONF_FILENAMES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DATA_IMAGES,
    DEFAULT_NAME,
    DOMAIN,
    IMAGE_EXPIRY_TIME,
    LOGGER,
    MAX_IMAGES,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    ImageData,
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


def _cleanup_images(image_storage: dict[str, ImageData], num_to_remove: int) -> None:
    """Remove old images to keep the storage size under the limit."""
    if num_to_remove <= 0:
        return

    if num_to_remove >= len(image_storage):
        image_storage.clear()
        return

    sorted_images = sorted(
        image_storage.items(),
        key=lambda item: item[1].timestamp,
    )

    for filename, _ in sorted_images[:num_to_remove]:
        image_storage.pop(filename, None)


async def _render_image(call: ServiceCall) -> ServiceResponse:
    """Render an image."""
    entry_id = call.data["config_entry"]
    entry = call.hass.config_entries.async_get_entry(entry_id)

    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={"config_entry": entry_id},
        )

    client: openai.AsyncClient = entry.runtime_data

    model_args = {
        "model": "gpt-image-1",
        "prompt": call.data[CONF_PROMPT],
        "background": call.data["background"],
        "size": call.data["size"],
        "quality": call.data["quality"],
        "moderation": call.data["moderation"],
        "output_format": "png",
        "n": 1,
    }
    if call.context.user_id:
        model_args["user"] = call.context.user_id

    repair_issue = False
    if model_args["size"] == "1024x1792":
        model_args["size"] = "1024x1536"
        repair_issue = True
    elif model_args["size"] == "1792x1024":
        model_args["size"] = "1536x1024"
        repair_issue = True
    if model_args["quality"] == "standard":
        model_args["quality"] = "medium"
        repair_issue = True
    elif model_args["quality"] == "hd":
        model_args["quality"] = "high"
        repair_issue = True
    if "style" in call.data:
        repair_issue = True

    try:
        try:
            response: ImagesResponse = await client.images.generate(**model_args)
        except openai.PermissionDeniedError as err:
            if "Verify Organization" not in str(err):
                raise
            LOGGER.debug("Permission denied error, fallback to dall-e-3")
            ir.async_create_issue(
                call.hass,
                DOMAIN,
                "organization_verification_required",
                is_fixable=False,
                is_persistent=True,
                learn_more_url="https://openai.com/index/image-generation-api/#get-started",
                severity=ir.IssueSeverity.WARNING,
                translation_key="organization_verification_required",
                translation_placeholders={
                    "platform_settings": "https://platform.openai.com/settings/organization/general"
                },
            )
            # Don't raise an issue about deprecated arguments
            # when there is no permissions for the new model:
            repair_issue = False

            model_args["model"] = "dall-e-3"
            model_args["style"] = call.data.get("style", "vivid")
            model_args["response_format"] = "b64_json"
            model_args.pop("output_format", None)
            model_args.pop("background", None)
            model_args.pop("moderation", None)
            if call.data["quality"] in ("standard", "hd"):
                model_args["quality"] = call.data["quality"]
            elif model_args["quality"] in ("medium", "low"):
                model_args["quality"] = "standard"
            elif model_args["quality"] in ("high", "auto"):
                model_args["quality"] = "hd"
            if model_args["size"] == "1024x1536":
                model_args["size"] = "1024x1792"
            elif model_args["size"] == "1536x1024":
                model_args["size"] = "1792x1024"
            elif model_args["size"] == "auto":
                model_args["size"] = "1024x1024"
            response = await client.images.generate(**model_args)
    except openai.OpenAIError as err:
        raise HomeAssistantError(f"Error generating image: {err}") from err

    if repair_issue:
        ir.async_create_issue(
            call.hass,
            DOMAIN,
            "generate_image_deprecated_params",
            is_fixable=False,
            is_persistent=True,
            learn_more_url="https://www.home-assistant.io/integrations/openai_conversation/",
            severity=ir.IssueSeverity.WARNING,
            translation_key="generate_image_deprecated_params",
        )

    if not response.data:
        raise HomeAssistantError("No image data returned")

    IMAGE_STORAGE = call.hass.data.setdefault(DATA_IMAGES, {})

    if len(IMAGE_STORAGE) + len(response.data) > MAX_IMAGES:
        _cleanup_images(
            IMAGE_STORAGE, len(response.data) + len(IMAGE_STORAGE) - MAX_IMAGES
        )

    for idx, response_data in enumerate(response.data):
        if not response_data.b64_json:
            raise HomeAssistantError("No image data returned")

        if not response_data.revised_prompt:
            response_data.revised_prompt = call.data[CONF_PROMPT]

        filename = f"{response.created}_{idx}.{model_args.get('output_format', 'png')}"

        IMAGE_STORAGE[filename] = ImageData(
            data=base64.b64decode(response_data.b64_json),
            timestamp=response.created,
            mime_type=f"image/{model_args.get('output_format', 'png')}",
            title=response_data.revised_prompt,
        )

        def _purge_image(filename: str, now: datetime) -> None:
            """Remove image from storage."""
            IMAGE_STORAGE.pop(filename, None)

        if IMAGE_EXPIRY_TIME > 0:
            async_track_point_in_time(
                call.hass,
                partial(_purge_image, filename),
                datetime.now() + timedelta(seconds=IMAGE_EXPIRY_TIME),
            )

        response_data.url = get_url(call.hass) + f"/api/{DOMAIN}/images/{filename}"

    return response.data[0].model_dump(exclude={"b64_json"})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up OpenAI Conversation."""

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
        _render_image,
        schema=vol.Schema(
            {
                vol.Required("config_entry"): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Required(CONF_PROMPT): cv.string,
                vol.Optional("size", default="auto"): vol.In(
                    (
                        "1024x1024",
                        "1536x1024",
                        "1024x1536",
                        "auto",
                        "1024x1792",
                        "1792x1024",
                    )
                ),
                vol.Optional("quality", default="auto"): vol.In(
                    ("auto", "high", "medium", "low", "standard", "hd")
                ),
                vol.Optional("background", default="auto"): vol.In(
                    ("transparent", "opaque", "auto")
                ),
                vol.Optional("style"): vol.In(("vivid", "natural")),
                vol.Optional("moderation", default="auto"): vol.In(("low", "auto")),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.http.register_view(ImageView)
    hass.http.register_view(ThumbnailView)

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

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OpenAI."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class ImageView(HomeAssistantView):
    """View to generated images."""

    url = f"/api/{DOMAIN}/images/{{filename}}"
    name = f"api:{DOMAIN}/images"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        filename: str,
    ) -> web.Response:
        """Serve image."""
        hass = request.app[KEY_HASS]
        IMAGE_STORAGE = hass.data.setdefault(DATA_IMAGES, {})
        image_data = IMAGE_STORAGE.get(filename)

        if image_data is None:
            raise web.HTTPNotFound

        return web.Response(
            body=image_data.data,
            content_type=image_data.mime_type,
        )


class ThumbnailView(HomeAssistantView):
    """View to generated images."""

    url = f"/api/{DOMAIN}/thumbnails/{{filename}}"
    name = f"api:{DOMAIN}/thumbnails"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        filename: str,
    ) -> web.Response:
        """Serve image."""
        hass = request.app[KEY_HASS]
        IMAGE_STORAGE = hass.data.setdefault(DATA_IMAGES, {})
        image_data = IMAGE_STORAGE.get(filename)

        if image_data is None:
            raise web.HTTPNotFound

        if image_data.thumbnail is None:
            image = Image.open(BytesIO(image_data.data))
            image.thumbnail((256, 256))
            image_bytes = BytesIO()
            image.save(image_bytes, format=image_data.mime_type.split("/")[-1].upper())
            image_data.thumbnail = image_bytes.getvalue()

        return web.Response(
            body=image_data.thumbnail,
            content_type=image_data.mime_type,
        )


async def async_update_options(hass: HomeAssistant, entry: OpenAIConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


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