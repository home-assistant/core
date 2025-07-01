"""The Google Generative AI Conversation integration."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from types import MappingProxyType

from google.genai import Client
from google.genai.errors import APIError, ClientError
from google.genai.types import File, FileState
from requests.exceptions import Timeout
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
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PROMPT,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DOMAIN,
    FILE_POLLING_INTERVAL_SECONDS,
    LOGGER,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    TIMEOUT_MILLIS,
)

SERVICE_GENERATE_CONTENT = "generate_content"
CONF_IMAGE_FILENAME = "image_filename"
CONF_FILENAMES = "filenames"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (
    Platform.CONVERSATION,
    Platform.TTS,
)

type GoogleGenerativeAIConfigEntry = ConfigEntry[Client]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Generative AI Conversation."""

    await async_migrate_integration(hass)

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
            model=RECOMMENDED_CHAT_MODEL,
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

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Unload GoogleGenerativeAI."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    return True


async def async_update_options(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> None:
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
        if use_existing:
            hass.config_entries.async_add_subentry(
                parent_entry,
                ConfigSubentry(
                    data=MappingProxyType(RECOMMENDED_TTS_OPTIONS),
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                ),
            )
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
                title=DEFAULT_TITLE,
                options={},
                version=2,
                minor_version=2,
            )


async def async_migrate_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 2 and entry.minor_version == 1:
        # Add TTS subentry which was missing in 2025.7.0b0
        if not any(
            subentry.subentry_type == "tts" for subentry in entry.subentries.values()
        ):
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(RECOMMENDED_TTS_OPTIONS),
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                ),
            )

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
