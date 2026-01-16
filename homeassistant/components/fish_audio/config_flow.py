"""Config flow for the Fish Audio integration."""

from __future__ import annotations

import logging
from typing import Any

from fishaudio import AsyncFishAudio
from fishaudio.exceptions import AuthenticationError, FishAudioError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    API_KEYS_URL,
    BACKEND_MODELS,
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_LATENCY,
    CONF_NAME,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_TITLE,
    CONF_USER_ID,
    CONF_VOICE_ID,
    DOMAIN,
    LATENCY_OPTIONS,
    SIGNUP_URL,
    SORT_BY_OPTIONS,
    TTS_SUPPORTED_LANGUAGES,
)
from .error import (
    CannotConnectError,
    CannotGetModelsError,
    InvalidAuthError,
    UnexpectedError,
)

_LOGGER = logging.getLogger(__name__)


def get_api_key_schema(default: str | None = None) -> vol.Schema:
    """Return the schema for API key input."""
    return vol.Schema(
        {vol.Required(CONF_API_KEY, default=default or vol.UNDEFINED): str}
    )


def get_filter_schema(options: dict[str, Any]) -> vol.Schema:
    """Return the schema for the filter step."""
    return vol.Schema(
        {
            vol.Optional(CONF_TITLE, default=options.get(CONF_TITLE, "")): str,
            vol.Optional(
                CONF_LANGUAGE, default=options.get(CONF_LANGUAGE, "Any")
            ): LanguageSelector(
                LanguageSelectorConfig(
                    languages=TTS_SUPPORTED_LANGUAGES,
                )
            ),
            vol.Optional(
                CONF_SORT_BY, default=options.get(CONF_SORT_BY, "task_count")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SORT_BY_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="sort_by",
                )
            ),
            vol.Optional(
                CONF_SELF_ONLY, default=options.get(CONF_SELF_ONLY, False)
            ): bool,
        }
    )


def get_model_selection_schema(
    options: dict[str, Any],
    model_options: list[SelectOptionDict],
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
            vol.Required(
                CONF_LATENCY,
                default=options.get(CONF_LATENCY, "balanced"),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=opt, label=opt)
                        for opt in LATENCY_OPTIONS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_NAME,
                default=options.get(CONF_NAME) or vol.UNDEFINED,
            ): str,
        }
    )


async def _validate_api_key(
    hass: HomeAssistant, api_key: str
) -> tuple[str, AsyncFishAudio]:
    """Validate the user input allows us to connect."""
    client = AsyncFishAudio(api_key=api_key)

    try:
        # Validate API key and get user info
        credit_info = await client.account.get_credits()
        user_id = credit_info.user_id
    except AuthenticationError as exc:
        raise InvalidAuthError(exc) from exc
    except FishAudioError as exc:
        raise CannotConnectError(exc) from exc
    except Exception as exc:
        raise UnexpectedError(exc) from exc

    return user_id, client


class FishAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fish Audio."""

    VERSION = 1
    client: AsyncFishAudio | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.client = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=get_api_key_schema(),
                errors={},
                description_placeholders={"signup_url": SIGNUP_URL},
            )

        errors: dict[str, str] = {}

        try:
            user_id, self.client = await _validate_api_key(
                self.hass, user_input[CONF_API_KEY]
            )
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        except UnexpectedError:
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            data: dict[str, Any] = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_USER_ID: user_id,
            }

            return self.async_create_entry(
                title="Fish Audio",
                data=data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=get_api_key_schema(),
            errors=errors,
            description_placeholders={
                "signup_url": SIGNUP_URL,
                "api_keys_url": API_KEYS_URL,
            },
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type]:
        """Return subentries supported by this integration."""
        return {"tts": FishAudioSubentryFlowHandler}


class FishAudioSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a tts entity."""

    config_data: dict[str, Any]
    models: list[SelectOptionDict]
    client: AsyncFishAudio

    def __init__(self) -> None:
        """Initialize the subentry flow handler."""
        super().__init__()
        self.models: list[SelectOptionDict] = []

    async def _async_get_models(
        self, self_only: bool, language: str | None, title: str | None, sort_by: str
    ) -> list[SelectOptionDict]:
        """Get the available models."""
        try:
            voices_response = await self.client.voices.list(
                self_only=self_only,
                language=language
                if language and language.strip() and language != "Any"
                else None,
                title=title if title and title.strip() else None,
                sort_by=sort_by,
            )
        except Exception as exc:
            raise CannotGetModelsError(exc) from exc

        voices = voices_response.items

        return [
            SelectOptionDict(
                value=voice.id,
                label=f"{voice.title} - {voice.task_count} uses",
            )
            for voice in voices
        ]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step."""
        self.config_data = {}
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.config_data = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        entry = self._get_entry()
        if entry.state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        self.client = entry.runtime_data

        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_model()

        return self.async_show_form(
            step_id="init",
            data_schema=get_filter_schema(self.config_data),
            errors={},
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the model selection step."""
        errors: dict[str, str] = {}

        if not self.models:
            try:
                self.models = await self._async_get_models(
                    self_only=self.config_data.get(CONF_SELF_ONLY, False),
                    language=self.config_data.get(CONF_LANGUAGE),
                    title=self.config_data.get(CONF_TITLE),
                    sort_by=self.config_data.get(CONF_SORT_BY, "task_count"),
                )
            except CannotGetModelsError:
                return self.async_abort(reason="cannot_connect")

            if not self.models:
                return self.async_abort(reason="no_models_found")

            if CONF_VOICE_ID not in self.config_data and self.models:
                self.config_data[CONF_VOICE_ID] = self.models[0]["value"]

        if user_input is not None:
            if (
                (voice_id := user_input.get(CONF_VOICE_ID))
                and (backend := user_input.get(CONF_BACKEND))
                and (name := user_input.get(CONF_NAME))
            ):
                self.config_data.update(user_input)
                unique_id = f"{voice_id}-{backend}"

                if self.source == SOURCE_USER:
                    return self.async_create_entry(
                        title=name,
                        data=self.config_data,
                        unique_id=unique_id,
                    )

                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=self.config_data,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="model",
            data_schema=get_model_selection_schema(self.config_data, self.models),
            errors=errors,
        )
