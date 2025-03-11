"""Config flow for PurpleAir integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    UnitOfLength,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.unit_conversion import DistanceConverter

from .config_schema import ConfigSchema
from .config_validation import ConfigValidation
from .const import (
    CONF_ADD_OPTIONS,
    CONF_ADD_SENSOR,
    CONF_MAP_LOCATION,
    CONF_NEARBY_SENSOR_LIST,
    CONF_REAUTH_CONFIRM,
    CONF_REAUTH_SUCCESSFUL,
    CONF_RECONFIGURE,
    CONF_RECONFIGURE_SUCCESSFUL,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    CONF_USER,
    DOMAIN,
    RADIUS_DEFAULT,
    SCHEMA_VERSION,
    TITLE,
)
from .options_flow import PurpleAirOptionsFlow


class PurpleAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for PurpleAir."""

    VERSION = SCHEMA_VERSION

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    @property
    def api_key_schema(self) -> vol.Schema:
        """API key schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY, default=self._flow_data.get(CONF_API_KEY)
                ): cv.string,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_USER, data_schema=self.api_key_schema
            )

        self._flow_data[CONF_API_KEY] = user_input.get(CONF_API_KEY)

        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_USER,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return await self.async_step_add_options()

    async def async_step_add_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add options."""
        return self.async_show_menu(
            step_id=CONF_ADD_OPTIONS,
            menu_options=[
                CONF_MAP_LOCATION,
                CONF_ADD_SENSOR,
            ],
        )

    @property
    def map_location_schema(self) -> vol.Schema:
        """Map location schema."""
        return self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                    ): LocationSelector(LocationSelectorConfig(radius=True)),
                }
            ),
            {
                CONF_LOCATION: {
                    CONF_LATITUDE: self._flow_data[CONF_LATITUDE],
                    CONF_LONGITUDE: self._flow_data[CONF_LONGITUDE],
                    CONF_RADIUS: self._flow_data[CONF_RADIUS],
                }
            },
        )

    async def async_step_map_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search sensors from map."""
        if not self._flow_data.get(CONF_LOCATION):
            self._flow_data[CONF_LATITUDE] = self.hass.config.latitude
            self._flow_data[CONF_LONGITUDE] = self.hass.config.longitude
            self._flow_data[CONF_RADIUS] = RADIUS_DEFAULT

        if user_input is None:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=self.map_location_schema,
            )

        self._flow_data[CONF_LATITUDE] = user_input[CONF_LOCATION][CONF_LATITUDE]
        self._flow_data[CONF_LONGITUDE] = user_input[CONF_LOCATION][CONF_LONGITUDE]
        self._flow_data[CONF_RADIUS] = user_input[CONF_LOCATION][CONF_RADIUS]

        validation = await ConfigValidation.async_validate_coordinates(
            self.hass,
            self._flow_data[CONF_API_KEY],
            self._flow_data[CONF_LATITUDE],
            self._flow_data[CONF_LONGITUDE],
            DistanceConverter.convert(
                self._flow_data[CONF_RADIUS],
                UnitOfLength.METERS,
                UnitOfLength.KILOMETERS,
            ),
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=self.map_location_schema,
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_LIST] = validation.data

        return await self.async_step_select_sensor()

    @property
    def sensor_select_schema(self) -> vol.Schema:
        """Selection list schema."""
        return vol.Schema(
            {
                vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=str(result.sensor.sensor_index),
                                label=f"{result.sensor.sensor_index} : {result.sensor.name}",
                            )
                            for result in self._flow_data[CONF_NEARBY_SENSOR_LIST]
                        ],
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                )
            }
        )

    async def async_step_select_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select sensor from list."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_SELECT_SENSOR,
                data_schema=self.sensor_select_schema,
            )

        data_config: dict[str, Any] = {
            CONF_API_KEY: self._flow_data[CONF_API_KEY],
        }
        options_config: dict[str, Any] = {
            CONF_SHOW_ON_MAP: False,
        }

        add_list = [int(index) for index in user_input[CONF_SENSOR_INDEX]]
        for index in add_list:
            ConfigSchema.async_add_sensor_to_sensor_list(options_config, index, None)

        title: str = await self._async_get_new_title()

        return self.async_create_entry(
            title=title, data=data_config, options=options_config
        )

    @property
    def add_sensor_schema(self) -> vol.Schema:
        """Add sensor schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_INDEX, default=self._flow_data.get(CONF_SENSOR_INDEX)
                ): cv.positive_int,
                vol.Optional(
                    CONF_SENSOR_READ_KEY,
                    default=vol.UNDEFINED
                    if not self._flow_data.get(CONF_SENSOR_READ_KEY)
                    or len(str(self._flow_data[CONF_SENSOR_READ_KEY])) == 0
                    else self._flow_data[CONF_SENSOR_READ_KEY],
                ): cv.string,
            }
        )

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add sensor by index and read key."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR,
                data_schema=self.add_sensor_schema,
            )

        self._flow_data[CONF_SENSOR_INDEX] = user_input[CONF_SENSOR_INDEX]
        self._flow_data[CONF_SENSOR_READ_KEY] = user_input.get(CONF_SENSOR_READ_KEY)

        validation = await ConfigValidation.async_validate_sensor(
            self.hass,
            self._flow_data[CONF_API_KEY],
            self._flow_data[CONF_SENSOR_INDEX],
            self._flow_data[CONF_SENSOR_READ_KEY],
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR,
                data_schema=self.add_sensor_schema,
                errors=validation.errors,
            )

        data_config: dict[str, Any] = {
            CONF_API_KEY: self._flow_data[CONF_API_KEY],
        }
        options_config: dict[str, Any] = {
            CONF_SHOW_ON_MAP: False,
        }

        ConfigSchema.async_add_sensor_to_sensor_list(
            options_config,
            self._flow_data[CONF_SENSOR_INDEX],
            self._flow_data[CONF_SENSOR_READ_KEY],
        )

        title: str = await self._async_get_new_title()

        return self.async_create_entry(
            title=title, data=data_config, options=options_config
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-auth step."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = user_input[CONF_API_KEY]

        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_REAUTH_SUCCESSFUL,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            self._flow_data[CONF_API_KEY] = self._get_reconfigure_entry().data.get(
                CONF_API_KEY
            )
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = user_input[CONF_API_KEY]

        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_RECONFIGURE_SUCCESSFUL,
        )

    async def _async_get_new_title(self) -> str:
        """Get title for new instance."""
        title: str = TITLE
        config_list = self.hass.config_entries.async_loaded_entries(DOMAIN)
        if len(config_list) > 0:
            title = f"{TITLE} ({len(config_list)})"
        return title

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PurpleAirOptionsFlow:
        """Define config flow to handle options."""
        return PurpleAirOptionsFlow()
