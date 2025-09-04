"""The Google Generative AI Conversation integration."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from types import MappingProxyType

from google.genai import Client
from google.genai.errors import APIError, ClientError
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
    DEFAULT_AI_TASK_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
    TIMEOUT_MILLIS,
)
from .entity import async_prepare_files_for_prompt

SERVICE_GENERATE_CONTENT = "generate_content"
CONF_IMAGE_FILENAME = "image_filename"
CONF_FILENAMES = "filenames"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (
    Platform.AI_TASK,
    Platform.CONVERSATION,
    Platform.STT,
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

        files = call.data[CONF_IMAGE_FILENAME] + call.data[CONF_FILENAMES]

        if files:
            for filename in files:
                if not hass.config.is_allowed_path(filename):
                    raise HomeAssistantError(
                        f"Cannot read `{filename}`, no access to path; "
                        "`allowlist_external_dirs` may need to be adjusted in "
                        "`configuration.yaml`"
                    )

            prompt_parts.extend(
                await async_prepare_files_for_prompt(
                    hass, client, [Path(filename) for filename in files]
                )
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
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> bool:
    """Set up Google Generative AI Conversation from a config entry."""

    try:
        client = await hass.async_add_executor_job(
            partial(Client, api_key=entry.data[CONF_API_KEY])
        )
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

    # Make sure we get enabled config entries first
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, tuple[ConfigEntry, bool]] = {}
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
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
            )
            api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]

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
        conversation_entity_id = entity_registry.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )

        if conversation_entity_id is not None:
            conversation_entity_entry = entity_registry.entities[conversation_entity_id]
            entity_disabled_by = conversation_entity_entry.disabled_by
            if (
                entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                # Device and entity registries will set the disabled_by flag to None
                # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
                # config entry, but we want to set it to DEVICE or USER instead,
                entity_disabled_by = (
                    er.RegistryEntryDisabler.DEVICE
                    if device
                    else er.RegistryEntryDisabler.USER
                )
            entity_registry.async_update_entity(
                conversation_entity_id,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                disabled_by=entity_disabled_by,
                new_unique_id=subentry.subentry_id,
            )

        if device is not None:
            # Device and entity registries will set the disabled_by flag to None
            # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
            # config entry, but we want to set it to USER instead,
            device_disabled_by = device.disabled_by
            if (
                device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                device_disabled_by = dr.DeviceEntryDisabler.USER
            device_registry.async_update_device(
                device.id,
                disabled_by=device_disabled_by,
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
            _add_ai_task_and_stt_subentries(hass, entry)
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_TITLE,
                options={},
                version=2,
                minor_version=4,
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

    if entry.version == 2 and entry.minor_version == 2:
        _add_ai_task_and_stt_subentries(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=3)

    if entry.version == 2 and entry.minor_version == 3:
        # Fix migration where the disabled_by flag was not set correctly.
        # We can currently only correct this for enabled config entries,
        # because migration does not run for disabled config entries. This
        # is asserted in tests, and if that behavior is changed, we should
        # correct also disabled config entries.
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entry.disabled_by is None:
            # If the config entry is not disabled, we need to set the disabled_by
            # flag on devices to USER, and on entities to DEVICE, if they are set
            # to CONFIG_ENTRY.
            for device in devices:
                if device.disabled_by is not dr.DeviceEntryDisabler.CONFIG_ENTRY:
                    continue
                device_registry.async_update_device(
                    device.id,
                    disabled_by=dr.DeviceEntryDisabler.USER,
                )
            for entity in entity_entries:
                if entity.disabled_by is not er.RegistryEntryDisabler.CONFIG_ENTRY:
                    continue
                entity_registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.DEVICE,
                )
        hass.config_entries.async_update_entry(entry, minor_version=4)

    LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True


def _add_ai_task_and_stt_subentries(
    hass: HomeAssistant, entry: GoogleGenerativeAIConfigEntry
) -> None:
    """Add AI Task and STT subentries to the config entry."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_AI_TASK_OPTIONS),
            subentry_type="ai_task_data",
            title=DEFAULT_AI_TASK_NAME,
            unique_id=None,
        ),
    )
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_STT_OPTIONS),
            subentry_type="stt",
            title=DEFAULT_STT_NAME,
            unique_id=None,
        ),
    )
