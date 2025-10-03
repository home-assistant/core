"""Schemas for the Fish Audio integration."""

import voluptuous as vol

from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BACKEND_MODELS,
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_VOICE_ID,
    SORT_BY_OPTIONS,
    TTS_SUPPORTED_LANGUAGES,
)
from .types import TTSConfigData


def get_api_key_schema(default: str | None = None) -> vol.Schema:
    """Return the schema for API key input."""
    return vol.Schema(
        {vol.Required(CONF_API_KEY, default=default or vol.UNDEFINED): str}
    )


# Backward compatibility
API_KEY_SCHEMA = get_api_key_schema()


def get_filter_schema(options: TTSConfigData) -> vol.Schema:
    """Return the schema for the filter step."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SELF_ONLY, default=options.get(CONF_SELF_ONLY, False)
            ): bool,
            vol.Optional(
                CONF_LANGUAGE, default=options.get(CONF_LANGUAGE, "en")
            ): LanguageSelector(
                LanguageSelectorConfig(
                    languages=TTS_SUPPORTED_LANGUAGES,
                )
            ),
            vol.Optional(
                CONF_SORT_BY, default=options.get(CONF_SORT_BY, "score")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SORT_BY_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def get_model_selection_schema(
    options: TTSConfigData, model_options: list[SelectOptionDict]
) -> vol.Schema:
    """Return the schema for the model selection step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_VOICE_ID,
                default=options.get(CONF_VOICE_ID, ""),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=model_options,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            ),
            vol.Required(
                CONF_BACKEND,
                default=options.get(CONF_BACKEND, "s1"),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=opt, label=opt) for opt in BACKEND_MODELS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def get_name_schema(options: TTSConfigData, default: str | None = None) -> vol.Schema:
    """Return the schema for the name input."""
    return vol.Schema({vol.Required(CONF_NAME, default=default or vol.UNDEFINED): str})
