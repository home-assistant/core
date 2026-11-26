"""Config flow for the Microsoft Text-to-Speech integration."""

import logging
from typing import Any, override

import probatio
from pycsspeechtts import pycsspeechtts
from requests.exceptions import RequestException

from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_REGION, CONF_TYPE, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.generated.microsoft_tts import SUPPORTED_LANGUAGES, SUPPORTED_REGIONS
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CONTOUR,
    CONF_GENDER,
    CONF_PITCH,
    CONF_RATE,
    CONF_VOLUME,
    DEFAULT_CONTOUR,
    DEFAULT_GENDER,
    DEFAULT_LANG,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_REGION,
    DEFAULT_TYPE,
    DEFAULT_VOLUME,
    DOMAIN,
    GENDERS,
    INTEGRATION_TITLE,
)
from .helpers import is_unauthorized

_LOGGER = logging.getLogger(__name__)

VOICES_URL = "https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts"

DEFAULT_OPTIONS = {
    CONF_RATE: DEFAULT_RATE,
    CONF_VOLUME: DEFAULT_VOLUME,
    CONF_PITCH: DEFAULT_PITCH,
    CONF_CONTOUR: DEFAULT_CONTOUR,
}

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
        probatio.Required(CONF_REGION, default=DEFAULT_REGION): SelectSelector(
            SelectSelectorConfig(
                options=sorted(SUPPORTED_REGIONS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
            )
        ),
        probatio.Required(CONF_LANG, default=DEFAULT_LANG): SelectSelector(
            SelectSelectorConfig(
                options=sorted(SUPPORTED_LANGUAGES),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_LANG,
                sort=True,
            )
        ),
        probatio.Required(CONF_GENDER, default=DEFAULT_GENDER): SelectSelector(
            SelectSelectorConfig(
                options=GENDERS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_GENDER,
            )
        ),
        probatio.Required(CONF_TYPE, default=DEFAULT_TYPE): TextSelector(),
    }
)

PERCENTAGE_SELECTOR = probatio.All(
    NumberSelector(
        NumberSelectorConfig(
            min=-100,
            max=100,
            step=1,
            mode=NumberSelectorMode.SLIDER,
            unit_of_measurement=PERCENTAGE,
        )
    ),
    probatio.Coerce(int),
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_RATE): PERCENTAGE_SELECTOR,
        probatio.Required(CONF_VOLUME): PERCENTAGE_SELECTOR,
        probatio.Optional(CONF_PITCH, default=DEFAULT_PITCH): TextSelector(),
        probatio.Optional(CONF_CONTOUR, default=DEFAULT_CONTOUR): TextSelector(),
    }
)


async def _async_validate_credentials(
    hass: HomeAssistant, api_key: str, region: str
) -> str | None:
    """Request an access token and return an error key if that fails."""
    try:
        await hass.async_add_executor_job(pycsspeechtts.TTSTranslator, api_key, region)
    except RequestException as err:
        return "invalid_api_key" if is_unauthorized(err) else "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return "unknown"
    return None


class MicrosoftConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microsoft Text-to-Speech."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            if error := await _async_validate_credentials(
                self.hass, user_input[CONF_API_KEY], user_input[CONF_REGION]
            ):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=INTEGRATION_TITLE, data=user_input, options=DEFAULT_OPTIONS
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={"voices_url": VOICES_URL},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import the YAML configuration of the legacy TTS platform."""
        self._async_abort_entries_match({CONF_API_KEY: import_data[CONF_API_KEY]})
        if error := await _async_validate_credentials(
            self.hass, import_data[CONF_API_KEY], import_data[CONF_REGION]
        ):
            return self.async_abort(reason=error)

        # Another YAML section with the same API key may have been imported meanwhile
        self._async_abort_entries_match({CONF_API_KEY: import_data[CONF_API_KEY]})
        return self.async_create_entry(
            title=INTEGRATION_TITLE,
            data={
                CONF_API_KEY: import_data[CONF_API_KEY],
                CONF_REGION: import_data[CONF_REGION],
                CONF_LANG: import_data[CONF_LANG],
                CONF_GENDER: import_data[CONF_GENDER].lower(),
                CONF_TYPE: import_data[CONF_TYPE],
            },
            options={key: import_data[key] for key in DEFAULT_OPTIONS},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> MicrosoftOptionsFlow:
        """Create the options flow."""
        return MicrosoftOptionsFlow()


class MicrosoftOptionsFlow(OptionsFlowWithReload):
    """Handle the prosody options of Microsoft Text-to-Speech."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
