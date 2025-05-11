"""The OpenAI Conversation integration."""

from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
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

from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
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
    issue_registry as ir,
    selector,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import raise_if_invalid_path

from .const import (
    CONF_CHAT_MODEL,
    CONF_FILENAMES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REASONING_EFFORT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DOMAIN,
    IMAGE_AUTH_EXPIRY_TIME,
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

    if not response.data or not response.data[0].b64_json:
        raise HomeAssistantError("No image data returned")

    if len(call.data[CONF_PROMPT]) <= 32:
        filename = f"{call.data[CONF_PROMPT].replace(' ', '_').replace('/', '_')}_{response.created}.png"
    else:
        filename = f"{hashlib.md5(call.data[CONF_PROMPT].encode('utf-8')).hexdigest()}_{response.created}.png"

    if DOMAIN in call.hass.config.media_dirs:
        source_dir_id = DOMAIN
        base_path = call.hass.config.media_dirs[source_dir_id]
        directory = Path(base_path)
        media_path = f"/media/{DOMAIN}/{filename}"
        file_path = directory / filename
    else:
        source_dir_id = list(call.hass.config.media_dirs)[0]
        base_path = call.hass.config.media_dirs[source_dir_id]
        directory = Path(base_path, DOMAIN)
        file_path = directory / filename
        media_path = f"/media/{source_dir_id}/{DOMAIN}/{filename}"

    raise_if_invalid_path(str(file_path))

    def save_image(b64_json: str, path: Path) -> None:
        """Save image to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as image_file:
            image_file.write(base64.b64decode(b64_json))

    await call.hass.async_add_executor_job(
        save_image, response.data[0].b64_json, file_path
    )

    LOGGER.debug("Image saved to %s", file_path)

    response.data[0].url = get_url(call.hass) + async_sign_path(
        call.hass,
        media_path,
        timedelta(seconds=IMAGE_AUTH_EXPIRY_TIME),
    )

    if not response.data[0].revised_prompt:
        response.data[0].revised_prompt = call.data[CONF_PROMPT]

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

        model: str = entry.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
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
                            file_id=filename,
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
                "max_output_tokens": entry.options.get(
                    CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS
                ),
                "top_p": entry.options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
                "temperature": entry.options.get(
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                ),
                "user": call.context.user_id,
                "store": False,
            }

            if model.startswith("o"):
                model_args["reasoning"] = {
                    "effort": entry.options.get(
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
