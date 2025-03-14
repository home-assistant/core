"""PurpleAir subentry flow."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    UnitOfLength,
)
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

from .config_validation import ConfigValidation
from .const import CONF_SENSOR_INDEX, CONF_SENSOR_READ_KEY

DEFAULT_RADIUS: Final[int] = 2000

CONF_ADD_MAP_LOCATION: Final[str] = "add_map_location"
CONF_ADD_OPTIONS: Final[str] = "add_options"
CONF_ADD_SENSOR_INDEX: Final[str] = "add_sensor_index"
CONF_NEARBY_SENSOR_LIST: Final[str] = "nearby_sensor_list"
CONF_SELECT_SENSOR: Final[str] = "select_sensor"


class PurpleAirSubentryFlow(ConfigSubentryFlow):
    """Handle subentry flow."""

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    def _parent_config_entry(self) -> ConfigEntry:
        if self.hass is None or self.handler is None:
            raise ValueError("Parent ConfigEntry not available")
        return self.hass.config_entries.async_get_known_entry(self.handler[0])

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle user initialization flow."""
        self._flow_data[CONF_API_KEY] = self._parent_config_entry().data[CONF_API_KEY]
        return await self.async_step_add_options()

    async def async_step_add_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select how to add sensor."""
        return self.async_show_menu(
            step_id=CONF_ADD_OPTIONS,
            menu_options=[
                CONF_ADD_MAP_LOCATION,
                CONF_ADD_SENSOR_INDEX,
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

    async def async_step_add_map_location(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Search sensors from map."""
        if not self._flow_data.get(CONF_LOCATION):
            self._flow_data[CONF_LATITUDE] = self.hass.config.latitude
            self._flow_data[CONF_LONGITUDE] = self.hass.config.longitude
            self._flow_data[CONF_RADIUS] = DEFAULT_RADIUS

        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ADD_MAP_LOCATION,
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
                step_id=CONF_ADD_MAP_LOCATION,
                data_schema=self.map_location_schema,
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_LIST] = validation.data

        return await self.async_step_select_sensor()

    @property
    def select_sensor_schema(self) -> vol.Schema:
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
                        multiple=False,
                    )
                )
            }
        )

    # Keep in sync with async_step_add_sensor_index()
    async def async_step_select_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select sensor from list."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_SELECT_SENSOR,
                data_schema=self.select_sensor_schema,
            )

        # TODO: Get sensor from name to use as title # pylint: disable=fixme
        # self._flow_data[CONF_NEARBY_SENSOR_LIST]

        # TODO: Test for uniqueness before creating the subentry # pylint: disable=fixme
        # _raise_if_subentry_unique_id_exists() -> already_configured
        return self.async_create_entry(
            title=str(user_input[CONF_SENSOR_INDEX]),
            data={CONF_SENSOR_INDEX: int(user_input[CONF_SENSOR_INDEX])},
            unique_id=str(user_input[CONF_SENSOR_INDEX]),
        )

    @property
    def sensor_index_schema(self) -> vol.Schema:
        """Add sensor index schema."""
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

    # Keep in sync with async_step_select_sensor()
    async def async_step_add_sensor_index(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add sensor by index and read key."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR_INDEX,
                data_schema=self.sensor_index_schema,
            )

        self._flow_data[CONF_SENSOR_INDEX] = int(user_input[CONF_SENSOR_INDEX])
        self._flow_data[CONF_SENSOR_READ_KEY] = user_input.get(CONF_SENSOR_READ_KEY)

        validation = await ConfigValidation.async_validate_sensor(
            self.hass,
            self._flow_data[CONF_API_KEY],
            self._flow_data[CONF_SENSOR_INDEX],
            self._flow_data[CONF_SENSOR_READ_KEY],
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR_INDEX,
                data_schema=self.sensor_index_schema,
                errors=validation.errors,
            )

        # TODO: Use sensor name as part of title # pylint: disable=fixme

        return self.async_create_entry(
            title=str(self._flow_data[CONF_SENSOR_INDEX]),
            data={
                CONF_SENSOR_INDEX: int(self._flow_data[CONF_SENSOR_INDEX]),
                CONF_SENSOR_READ_KEY: self._flow_data[CONF_SENSOR_READ_KEY],
            },
            unique_id=str(self._flow_data[CONF_SENSOR_INDEX]),
        )
