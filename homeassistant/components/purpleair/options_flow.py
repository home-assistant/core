"""Options flow for PurpleAir integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    UnitOfLength,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
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
    CONF_ADD_SENSOR,
    CONF_ALREADY_CONFIGURED,
    CONF_INIT,
    CONF_MAP_LOCATION,
    CONF_NEARBY_SENSOR_LIST,
    CONF_REMOVE_SENSOR,
    CONF_SELECT_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    CONF_SETTINGS,
    DOMAIN,
    RADIUS_DEFAULT,
)
from .coordinator import PurpleAirDataUpdateCoordinator


class PurpleAirOptionsFlow(OptionsFlow):
    """Handle options flow for PurpleAir."""

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set options."""
        return self.async_show_menu(
            step_id=CONF_INIT,
            menu_options=[
                CONF_MAP_LOCATION,
                CONF_ADD_SENSOR,
                CONF_REMOVE_SENSOR,
                CONF_SETTINGS,
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
            self.config_entry.data[CONF_API_KEY],
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

        add_list = [int(index) for index in user_input[CONF_SENSOR_INDEX]]
        index_list = ConfigSchema.async_get_sensor_index_list(
            dict(self.config_entry.options)
        )
        assert index_list is not None
        if any(index in index_list for index in add_list):
            return self.async_abort(reason=CONF_ALREADY_CONFIGURED)

        options = deepcopy(dict(self.config_entry.options))
        for index in add_list:
            ConfigSchema.async_add_sensor_to_sensor_list(options, index, None)

        return self.async_create_entry(data=options)

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
            self.config_entry.data[CONF_API_KEY],
            self._flow_data[CONF_SENSOR_INDEX],
            self._flow_data[CONF_SENSOR_READ_KEY],
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR,
                data_schema=self.add_sensor_schema,
                errors=validation.errors,
            )

        sensor_index = int(self._flow_data[CONF_SENSOR_INDEX])
        index_list = ConfigSchema.async_get_sensor_index_list(
            dict(self.config_entry.options)
        )
        assert index_list is not None
        if sensor_index in index_list:
            return self.async_abort(reason=CONF_ALREADY_CONFIGURED)

        options = deepcopy(dict(self.config_entry.options))
        ConfigSchema.async_add_sensor_to_sensor_list(
            options, sensor_index, self._flow_data[CONF_SENSOR_READ_KEY]
        )

        return self.async_create_entry(data=options)

    @property
    def remove_sensor_schema(self) -> vol.Schema:
        """Selection list schema."""
        device_list = dr.async_entries_for_config_entry(
            dr.async_get(self.hass), self.config_entry.entry_id
        )

        sensor_list = [
            (int(identifier[1]), device.name)
            for device in device_list
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        ]

        select_list = [
            SelectOptionDict(
                value=str(sensor[0]),
                label=f"({sensor[0]}) {sensor[1]}",
            )
            for sensor in sensor_list
        ]

        return vol.Schema(
            {
                vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                    SelectSelectorConfig(
                        options=select_list,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

    async def async_step_remove_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove sensor."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_REMOVE_SENSOR, data_schema=self.remove_sensor_schema
            )

        sensor_index = int(user_input[CONF_SENSOR_INDEX])

        options = deepcopy(dict(self.config_entry.options))
        ConfigSchema.async_remove_sensor_from_sensor_list(options, sensor_index)

        coordinator: PurpleAirDataUpdateCoordinator = self.config_entry.runtime_data
        coordinator.async_delete_orphans_from_device_registry(options=options)

        return self.async_create_entry(data=options)

    @property
    def settings_schema(self) -> vol.Schema:
        """Settings schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_ON_MAP,
                    default=self.config_entry.options.get(CONF_SHOW_ON_MAP, False),
                ): bool
            }
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage settings."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_SETTINGS, data_schema=self.settings_schema
            )

        options = deepcopy(dict(self.config_entry.options))
        options[CONF_SHOW_ON_MAP] = user_input.get(CONF_SHOW_ON_MAP, False)

        return self.async_create_entry(data=options)
