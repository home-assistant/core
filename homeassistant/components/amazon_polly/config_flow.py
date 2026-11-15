"""Config flow for the Amazon Polly integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.generated.amazon_polly import (
    SUPPORTED_ENGINES,
    SUPPORTED_REGIONS,
    SUPPORTED_VOICES,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_ENGINE,
    CONF_OUTPUT_FORMAT,
    CONF_REGION,
    CONF_SAMPLE_RATE,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEXT_TYPE,
    CONF_VOICE,
    DEFAULT_ENGINE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_REGION,
    DEFAULT_TEXT_TYPE,
    DEFAULT_VOICE,
    DOMAIN,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_SAMPLE_RATES,
    SUPPORTED_SAMPLE_RATES_MAP,
    SUPPORTED_TEXT_TYPES,
)
from .helpers import (
    AmazonPollyConfigEntry,
    CannotConnect,
    InvalidAuth,
    async_connect,
    unique_id_for,
)

_LOGGER = logging.getLogger(__name__)

OPTION_KEYS = (
    CONF_VOICE,
    CONF_ENGINE,
    CONF_OUTPUT_FORMAT,
    CONF_SAMPLE_RATE,
    CONF_TEXT_TYPE,
)

CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ACCESS_KEY_ID): TextSelector(),
        probatio.Required(probatio.Secret(CONF_SECRET_ACCESS_KEY)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

USER_SCHEMA = probatio.Schema(
    {
        # custom_value makes the frontend render a searchable picker.
        probatio.Required(CONF_REGION, default=DEFAULT_REGION): SelectSelector(
            SelectSelectorConfig(
                options=sorted(
                    (
                        SelectOptionDict(value=region, label=f"{name} – {region}")
                        for region, name in SUPPORTED_REGIONS.items()
                    ),
                    key=lambda option: option["label"],
                ),
                custom_value=True,
                sort=False,
            )
        ),
    }
).extend(CREDENTIALS_SCHEMA.schema)


def _title(region: str) -> str:
    return f"Amazon Polly ({region})"


async def _async_validate(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> dict[str, str]:
    """Check the region and credentials, returning form errors."""
    if user_input[CONF_REGION] not in SUPPORTED_REGIONS:
        return {CONF_REGION: "invalid_region"}
    try:
        data = await async_connect(
            hass,
            region=user_input[CONF_REGION],
            access_key_id=user_input[CONF_ACCESS_KEY_ID],
            secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
        )
    except InvalidAuth:
        return {"base": "invalid_auth"}
    except CannotConnect:
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return {"base": "unknown"}
    await data.client.__aexit__(None, None, None)
    return {}


class AmazonPollyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amazon Polly."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id_for(user_input[CONF_ACCESS_KEY_ID], user_input[CONF_REGION])
            )
            self._abort_if_unique_id_configured()
            if not (errors := await _async_validate(self.hass, user_input)):
                return self.async_create_entry(
                    title=_title(user_input[CONF_REGION]), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a YAML configured Amazon Polly platform."""
        await self.async_set_unique_id(
            unique_id_for(import_data[CONF_ACCESS_KEY_ID], import_data[CONF_REGION])
        )
        self._abort_if_unique_id_configured()
        if errors := await _async_validate(self.hass, import_data):
            return self.async_abort(reason=errors["base"])
        return self.async_create_entry(
            title=_title(import_data[CONF_REGION]),
            data={
                CONF_REGION: import_data[CONF_REGION],
                CONF_ACCESS_KEY_ID: import_data[CONF_ACCESS_KEY_ID],
                CONF_SECRET_ACCESS_KEY: import_data[CONF_SECRET_ACCESS_KEY],
            },
            options={
                key: import_data[key] for key in OPTION_KEYS if key in import_data
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle rejected AWS credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new AWS credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {CONF_REGION: entry.data[CONF_REGION], **user_input}
            result = await self._async_update_credentials(entry, user_input, errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA,
                {CONF_ACCESS_KEY_ID: entry.data[CONF_ACCESS_KEY_ID]},
            ),
            errors=errors,
            description_placeholders={"title": entry.title},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the region or AWS credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._async_update_credentials(entry, user_input, errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                user_input
                or {
                    CONF_REGION: entry.data[CONF_REGION],
                    CONF_ACCESS_KEY_ID: entry.data[CONF_ACCESS_KEY_ID],
                },
            ),
            errors=errors,
        )

    async def _async_update_credentials(
        self,
        entry: ConfigEntry,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Validate new credentials and update the entry, allowing key rotation."""
        unique_id = unique_id_for(
            user_input[CONF_ACCESS_KEY_ID], user_input[CONF_REGION]
        )
        if unique_id != entry.unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
        if new_errors := await _async_validate(self.hass, user_input):
            errors.update(new_errors)
            return None
        return self.async_update_reload_and_abort(
            entry,
            unique_id=unique_id,
            title=entry.title
            if self.source == SOURCE_REAUTH
            else _title(user_input[CONF_REGION]),
            data_updates=user_input,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: AmazonPollyConfigEntry,
    ) -> AmazonPollyOptionsFlow:
        """Create the options flow."""
        return AmazonPollyOptionsFlow()


class AmazonPollyOptionsFlow(OptionsFlowWithReload):
    """Amazon Polly default voice and audio options."""

    config_entry: AmazonPollyConfigEntry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        voices = self._loaded_voices()
        errors: dict[str, str] = {}
        if user_input is not None:
            output_format = user_input[CONF_OUTPUT_FORMAT]
            sample_rate = user_input.get(CONF_SAMPLE_RATE)
            if (
                sample_rate is not None
                and sample_rate not in SUPPORTED_SAMPLE_RATES_MAP[output_format]
            ):
                errors[CONF_SAMPLE_RATE] = "invalid_sample_rate"
            elif voices is not None and user_input[CONF_ENGINE] not in voices.get(
                user_input[CONF_VOICE], {}
            ).get("SupportedEngines", []):
                errors[CONF_ENGINE] = "engine_not_supported"
            else:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                self._options_schema(voices),
                user_input or self.config_entry.options,
            ),
            errors=errors,
        )

    def _loaded_voices(self) -> dict[str, dict[str, Any]] | None:
        """Return the voices Polly reported, if the entry is loaded."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return None
        return self.config_entry.runtime_data.voices

    @staticmethod
    def _options_schema(voices: dict[str, dict[str, Any]] | None) -> probatio.Schema:
        if voices is None:
            voice_options = [
                SelectOptionDict(value=voice, label=voice)
                for voice in sorted(SUPPORTED_VOICES)
            ]
            engines = sorted(SUPPORTED_ENGINES)
        else:
            voice_options = sorted(
                (
                    SelectOptionDict(
                        value=voice_id,
                        label=f"{voice.get('Name', voice_id)} ({voice.get('LanguageCode')}, {voice.get('Gender')})",
                    )
                    for voice_id, voice in voices.items()
                ),
                key=lambda option: option["label"],
            )
            engines = sorted(
                {
                    engine
                    for voice in voices.values()
                    for engine in voice.get("SupportedEngines", [])
                }
            )

        def dropdown(options: list[str] | list[SelectOptionDict]) -> SelectSelector:
            return SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )

        return probatio.Schema(
            {
                probatio.Required(CONF_VOICE, default=DEFAULT_VOICE): dropdown(
                    voice_options
                ),
                probatio.Required(CONF_ENGINE, default=DEFAULT_ENGINE): dropdown(
                    engines
                ),
                probatio.Required(
                    CONF_OUTPUT_FORMAT, default=DEFAULT_OUTPUT_FORMAT
                ): dropdown(sorted(SUPPORTED_OUTPUT_FORMATS)),
                probatio.Optional(CONF_SAMPLE_RATE): dropdown(
                    sorted(SUPPORTED_SAMPLE_RATES, key=int)
                ),
                probatio.Required(CONF_TEXT_TYPE, default=DEFAULT_TEXT_TYPE): dropdown(
                    sorted(SUPPORTED_TEXT_TYPES)
                ),
            }
        )
