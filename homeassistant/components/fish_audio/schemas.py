"""Schemas for the Fish Audio integration."""

from typing import Any

import voluptuous as vol

from homeassistant.helpers.selector import (
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
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_VOICE_ID,
    LANGUAGE_OPTIONS,
    SORT_BY_OPTIONS,
)

API_KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def get_filter_schema(options: dict[str, Any]) -> vol.Schema:
    """Return the schema for the filter step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SELF_ONLY,
                default=options.get(CONF_SELF_ONLY, False),
            ): bool,
            vol.Required(
                CONF_LANGUAGE,
                default=options.get(CONF_LANGUAGE, "en"),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=opt["value"], label=opt["label"])
                        for opt in LANGUAGE_OPTIONS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_SORT_BY,
                default=options.get(CONF_SORT_BY, "score"),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SORT_BY_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def get_model_selection_schema(
    options: dict[str, Any], model_options: list[SelectOptionDict]
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
