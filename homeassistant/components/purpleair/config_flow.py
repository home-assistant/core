"""Config flow for PurpleAir integration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Final, cast

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SHOW_ON_MAP,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowHandler
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

from .const import CONF_SENSOR_INDEX, DOMAIN, LOGGER, SCHEMA_VERSION
from .coordinator import (
    PurpleAirDataUpdateCoordinator,
    SensorInfo,
    async_add_sensor_to_sensor_list,
    async_get_api,
    async_get_sensor_device_info_list,
    async_get_sensor_index_list,
    async_get_sensor_nearby_sensors_list,
    async_remove_sensor_from_sensor_list,
)

CONF_NEARBY_SENSOR_LIST: Final = "nearby_sensor_list"
CONF_MAP_LOCATION: Final = "map_location"
CONF_REMOVE_SENSOR: Final = "remove_sensor"
CONF_SETTINGS: Final = "settings"
CONF_INIT: Final = "init"
CONF_USER: Final = "user"
CONF_SELECT_SENSOR: Final = "select_sensor"

CONF_RADIUS_DEFAULT: Final = 2000

LIMIT_RESULTS: Final = 25
TITLE: Final = "PurpleAir"


def async_get_sensor_select_schema(sensor_list: list[SensorInfo]) -> vol.Schema:
    """Return schema for selecting sensor from list."""
    selection_list = [
        SelectOptionDict(
            value=str(sensor.index),
            label=f"{sensor.index} : {sensor.name}",
        )
        for sensor in sensor_list
    ]

    return vol.Schema(
        {
            vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                # TODO: Allow multiple selections # pylint: disable=fixme
                SelectSelectorConfig(
                    options=selection_list, mode=SelectSelectorMode.LIST, multiple=False
                )
            )
        }
    )


def async_get_location_schema(flow_handler: FlowHandler) -> vol.Schema:
    """Return schema for selecting location from map."""
    return flow_handler.add_suggested_values_to_schema(
        vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION,
                ): LocationSelector(LocationSelectorConfig(radius=True)),
            }
        ),
        {
            CONF_LOCATION: {
                CONF_LATITUDE: flow_handler.hass.config.latitude,
                CONF_LONGITUDE: flow_handler.hass.config.longitude,
                CONF_RADIUS: CONF_RADIUS_DEFAULT,
            }
        },
    )


@dataclass
class ValidationResult:
    """Define a validation result."""

    data: Any = None
    errors: dict[str, Any] = field(default_factory=dict)


async def async_validate_api_key(hass: HomeAssistant, api_key: str) -> ValidationResult:
    """Validate an API key.

    This method returns a dictionary of errors (if appropriate).
    """
    api = async_get_api(hass, api_key)
    errors = {}

    try:
        await api.async_check_api_key()
    except InvalidApiKeyError:
        errors["base"] = "invalid_api_key"
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while checking API key: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # noqa: BLE001
        LOGGER.exception("Unexpected exception while checking API key: %s", err)
        errors["base"] = "unknown"

    if errors:
        return ValidationResult(errors=errors)

    return ValidationResult(data=None)


async def async_validate_coordinates(
    hass: HomeAssistant,
    api_key: str,
    latitude: float,
    longitude: float,
    distance: float,
) -> ValidationResult:
    """Validate coordinates."""
    api = async_get_api(hass, api_key)
    errors = {}

    try:
        nearby_sensor_results = await api.sensors.async_get_nearby_sensors(
            ["name"], latitude, longitude, distance, limit_results=LIMIT_RESULTS
        )
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # noqa: BLE001
        LOGGER.exception("Unexpected exception while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    else:
        if not nearby_sensor_results:
            errors["base"] = "no_sensors_found"

    if errors:
        return ValidationResult(errors=errors)

    return ValidationResult(data=nearby_sensor_results)


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

        api_key = user_input[CONF_API_KEY]

        validation = await async_validate_api_key(self.hass, api_key)
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_USER,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        await self.async_set_unique_id(api_key)
        self._abort_if_unique_id_configured()

        self._flow_data[CONF_API_KEY] = api_key

        return await self.async_step_map_location()

    async def async_step_map_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search sensors from map."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=async_get_location_schema(cast(FlowHandler, self)),
            )

        validation = await async_validate_coordinates(
            self.hass,
            self._flow_data[CONF_API_KEY],
            user_input[CONF_LOCATION][CONF_LATITUDE],
            user_input[CONF_LOCATION][CONF_LONGITUDE],
            DistanceConverter.convert(
                user_input[CONF_LOCATION][CONF_RADIUS],
                UnitOfLength.METERS,
                UnitOfLength.KILOMETERS,
            ),
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=async_get_location_schema(cast(FlowHandler, self)),
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_LIST] = validation.data

        return await self.async_step_select_sensor()

    async def async_step_select_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select sensor from list."""
        if user_input is None:
            options = self._flow_data.pop(CONF_NEARBY_SENSOR_LIST)
            return self.async_show_form(
                step_id=CONF_SELECT_SENSOR,
                data_schema=async_get_sensor_select_schema(
                    async_get_sensor_nearby_sensors_list(options)
                ),
            )

        data_config: dict[str, Any] = {
            CONF_API_KEY: self._flow_data[CONF_API_KEY],
        }
        options_config: dict[str, Any] = {
            CONF_SHOW_ON_MAP: False,
        }
        async_add_sensor_to_sensor_list(
            options_config,
            int(user_input[CONF_SENSOR_INDEX]),
            None,
        )

        title: str = TITLE
        config_list = self.hass.config_entries.async_loaded_entries(DOMAIN)
        if len(config_list) > 0:
            title = f"{TITLE} ({len(config_list)})"

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
                step_id="reauth_confirm",
                data_schema=self.api_key_schema,
            )

        api_key = user_input[CONF_API_KEY]

        validation = await async_validate_api_key(self.hass, api_key)
        if validation.errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        self._flow_data[CONF_API_KEY] = self._get_reconfigure_entry().data.get(
            CONF_API_KEY
        )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PurpleAirOptionsFlow:
        """Define config flow to handle options."""
        return PurpleAirOptionsFlow()


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
            menu_options=[CONF_MAP_LOCATION, CONF_REMOVE_SENSOR, CONF_SETTINGS],
        )

    async def async_step_map_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search sensors from map."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=async_get_location_schema(cast(FlowHandler, self)),
            )

        validation = await async_validate_coordinates(
            self.hass,
            self.config_entry.data[CONF_API_KEY],
            user_input[CONF_LOCATION][CONF_LATITUDE],
            user_input[CONF_LOCATION][CONF_LONGITUDE],
            DistanceConverter.convert(
                user_input[CONF_LOCATION][CONF_RADIUS],
                UnitOfLength.METERS,
                UnitOfLength.KILOMETERS,
            ),
        )

        if validation.errors:
            return self.async_show_form(
                step_id=CONF_MAP_LOCATION,
                data_schema=async_get_location_schema(cast(FlowHandler, self)),
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_LIST] = validation.data

        return await self.async_step_select_sensor()

    async def async_step_select_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select sensor from list."""
        if user_input is None:
            options = self._flow_data.pop(CONF_NEARBY_SENSOR_LIST)
            return self.async_show_form(
                step_id=CONF_SELECT_SENSOR,
                data_schema=async_get_sensor_select_schema(
                    async_get_sensor_nearby_sensors_list(options)
                ),
            )

        sensor_index = int(user_input[CONF_SENSOR_INDEX])
        index_list = async_get_sensor_index_list(dict(self.config_entry.options))
        assert index_list is not None
        if sensor_index in index_list:
            return self.async_abort(reason="already_configured")

        options = deepcopy(dict(self.config_entry.options))
        async_add_sensor_to_sensor_list(options, sensor_index, None)

        return self.async_create_entry(data=options)

    async def async_step_remove_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove sensor."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_REMOVE_SENSOR,
                data_schema=async_get_sensor_select_schema(
                    async_get_sensor_device_info_list(
                        self.hass, self.config_entry.entry_id
                    )
                ),
            )

        sensor_index = int(user_input[CONF_SENSOR_INDEX])

        options = deepcopy(dict(self.config_entry.options))
        async_remove_sensor_from_sensor_list(options, sensor_index)

        coordinator: PurpleAirDataUpdateCoordinator = self.config_entry.runtime_data
        coordinator.async_delete_orphans_from_device_registry()

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
