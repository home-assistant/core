"""Adds config flow for Scrape integration."""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, METHODS
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.trigger_template_entity import CONF_AVAILABILITY

from . import COMBINED_SCHEMA
from .const import (
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_ENCODING,
    DEFAULT_NAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

RESOURCE_SETUP = vol.Schema(
    {
        vol.Required(CONF_RESOURCE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
            SelectSelectorConfig(options=METHODS, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(CONF_PAYLOAD): ObjectSelector(),
        vol.Required("auth"): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_AUTHENTICATION): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                HTTP_BASIC_AUTHENTICATION,
                                HTTP_DIGEST_AUTHENTICATION,
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, autocomplete="username"
                        )
                    ),
                    vol.Optional(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            data_entry_flow.SectionConfig(collapsed=True),
        ),
        vol.Required("advanced"): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_HEADERS): ObjectSelector(),
                    vol.Optional(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): BooleanSelector(),
                    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
                        NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_ENCODING, default=DEFAULT_ENCODING
                    ): TextSelector(),
                }
            ),
            data_entry_flow.SectionConfig(collapsed=True),
        ),
    }
)

SENSOR_SETUP = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_SELECT): TextSelector(),
        vol.Optional(CONF_INDEX, default=0): vol.All(
            NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Coerce(int),
        ),
        vol.Required("advanced"): data_entry_flow.section(
            vol.Schema(
                {
                    vol.Optional(CONF_ATTRIBUTE): TextSelector(),
                    vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
                    vol.Optional(CONF_AVAILABILITY): TemplateSelector(),
                    vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                cls.value
                                for cls in SensorDeviceClass
                                if cls != SensorDeviceClass.ENUM
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="device_class",
                            sort=True,
                        )
                    ),
                    vol.Optional(CONF_STATE_CLASS): SelectSelector(
                        SelectSelectorConfig(
                            options=[cls.value for cls in SensorStateClass],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="state_class",
                            sort=True,
                        )
                    ),
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
                        SelectSelectorConfig(
                            options=[cls.value for cls in UnitOfTemperature],
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="unit_of_measurement",
                            sort=True,
                        )
                    ),
                }
            ),
            data_entry_flow.SectionConfig(collapsed=True),
        ),
    }
)


async def validate_rest_setup(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate rest setup."""
    config = deepcopy(user_input)
    config.update(config.pop("advanced", {}))
    config.update(config.pop("auth", {}))
    rest_config: dict[str, Any] = COMBINED_SCHEMA(config)
    try:
        rest = create_rest_data_from_config(hass, rest_config)
        await rest.async_update()
    except Exception:
        _LOGGER.exception("Error when getting resource %s", config[CONF_RESOURCE])
        return {"base": "resource_error"}
    if rest.data is None:
        return {"base": "no_data"}
    return {}


class ScrapeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Scrape configuration flow."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ScrapeOptionFlow:
        """Get the options flow for this handler."""
        return ScrapeOptionFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"entity": ScrapeSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User flow to create a sensor subentry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await validate_rest_setup(self.hass, user_input)
            title = user_input[CONF_RESOURCE]
            if not errors:
                return self.async_create_entry(data={}, options=user_input, title=title)

        return self.async_show_form(
            step_id="user", data_schema=RESOURCE_SETUP, errors=errors
        )


class ScrapeOptionFlow(OptionsFlow):
    """Scrape Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Scrape options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await validate_rest_setup(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                RESOURCE_SETUP,
                self.config_entry.options,
            ),
            errors=errors,
        )


class ScrapeSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a sensor subentry."""
        if user_input is not None:
            title = user_input.pop("name")
            return self.async_create_entry(data=user_input, title=title)

        return self.async_show_form(step_id="user", data_schema=SENSOR_SETUP)
