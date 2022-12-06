"""Config flow for PurpleAir integration."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, cast

from aiopurpleair import API
from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_LAST_UPDATE_SENSOR_ADD, CONF_SENSOR_INDICES, DOMAIN, LOGGER

CONF_DISTANCE = "distance"
CONF_NEARBY_SENSOR_OPTIONS = "nearby_sensor_options"
CONF_SENSOR_DEVICE_ID = "sensor_device_id"
CONF_SENSOR_INDEX = "sensor_index"

DEFAULT_DISTANCE = 5

API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


@callback
def async_get_api(hass: HomeAssistant, api_key: str) -> API:
    """Get an aiopurpleair API object."""
    session = aiohttp_client.async_get_clientsession(hass)
    return API(api_key, session=session)


@callback
def async_get_coordinates_schema(hass: HomeAssistant) -> vol.Schema:
    """Define a schema for searching for sensors near a coordinate pair."""
    return vol.Schema(
        {
            vol.Inclusive(
                CONF_LATITUDE, "coords", default=hass.config.latitude
            ): cv.latitude,
            vol.Inclusive(
                CONF_LONGITUDE, "coords", default=hass.config.longitude
            ): cv.longitude,
            vol.Optional(CONF_DISTANCE, default=DEFAULT_DISTANCE): cv.positive_int,
        }
    )


@callback
def async_get_nearby_sensors_options(
    nearby_sensor_results: list[NearbySensorResult],
) -> list[SelectOptionDict]:
    """Return a set of nearby sensors as SelectOptionDict objects."""
    return [
        SelectOptionDict(
            value=str(result.sensor.sensor_index),
            label=f"{result.sensor.name} ({round(result.distance, 1)} km away)",
        )
        for result in nearby_sensor_results
    ]


@callback
def async_get_nearby_sensors_schema(options: list[SelectOptionDict]) -> vol.Schema:
    """Define a schema for selecting a sensor from a list."""
    return vol.Schema(
        {
            vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )
        }
    )


@callback
def async_get_remove_sensor_options(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[SelectOptionDict]:
    """Return a set of already-configured sensors as SelectOptionDict objects."""
    device_registry = dr.async_get(hass)
    return [
        SelectOptionDict(value=device_entry.id, label=cast(str, device_entry.name))
        for device_entry in device_registry.devices.values()
        if config_entry.entry_id in device_entry.config_entries
    ]


@callback
def async_get_remove_sensor_schema(sensors: list[SelectOptionDict]) -> vol.Schema:
    """Define a schema removing a sensor."""
    return vol.Schema(
        {
            vol.Required(CONF_SENSOR_DEVICE_ID): SelectSelector(
                SelectSelectorConfig(options=sensors, mode=SelectSelectorMode.DROPDOWN)
            )
        }
    )


@callback
def async_get_sensor_index(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> int:
    """Get the sensor index related to a config and device entry.

    Note that this method expects that there will always be a single sensor index per
    DeviceEntry.
    """
    device_registry = dr.async_get(hass)
    device_entry = cast(dr.DeviceEntry, device_registry.async_get(device_entry.id))

    [sensor_index] = [
        sensor_index
        for sensor_index in config_entry.options[CONF_SENSOR_INDICES]
        if (DOMAIN, str(sensor_index)) in device_entry.identifiers
    ]

    return cast(int, sensor_index)


@callback
def async_untrack_sensor_index(
    config_entry: ConfigEntry, sensor_index: int
) -> dict[str, Any]:
    """Untrack a sensor index from a config entry and return the current index list."""
    options = deepcopy({**config_entry.options})
    options[CONF_LAST_UPDATE_SENSOR_ADD] = False
    options[CONF_SENSOR_INDICES].remove(sensor_index)
    return options


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
    except Exception as err:  # pylint: disable=broad-except
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

    print("AARON")
    try:
        nearby_sensor_results = await api.sensors.async_get_nearby_sensors(
            ["name"], latitude, longitude, distance, limit_results=5
        )
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    else:
        if not nearby_sensor_results:
            errors["base"] = "no_sensors_near_coordinates"

    if errors:
        return ValidationResult(errors=errors)

    return ValidationResult(data=nearby_sensor_results)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PurpleAir."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PurpleAirOptionsFlowHandler:
        """Define the config flow to handle options."""
        return PurpleAirOptionsFlowHandler(config_entry)

    async def async_step_by_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the discovery of sensors near a latitude/longitude."""
        if user_input is None:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
            )

        validation = await async_validate_coordinates(
            self.hass,
            self._flow_data[CONF_API_KEY],
            user_input[CONF_LATITUDE],
            user_input[CONF_LONGITUDE],
            user_input[CONF_DISTANCE],
        )

        if validation.errors:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_OPTIONS] = async_get_nearby_sensors_options(
            validation.data
        )

        return await self.async_step_choose_sensor()

    async def async_step_choose_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the selection of a sensor."""
        if user_input is None:
            options = self._flow_data.pop(CONF_NEARBY_SENSOR_OPTIONS)
            return self.async_show_form(
                step_id="choose_sensor",
                data_schema=async_get_nearby_sensors_schema(options),
            )

        return self.async_create_entry(
            title=self._flow_data[CONF_API_KEY][:5],
            data=self._flow_data,
            # Note that we store the sensor indices in options so that later on, we can
            # add/remove additional sensors via an options flow:
            options={CONF_SENSOR_INDICES: [int(user_input[CONF_SENSOR_INDEX])]},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=API_KEY_SCHEMA)

        api_key = user_input[CONF_API_KEY]

        await self.async_set_unique_id(api_key)
        self._abort_if_unique_id_configured()

        validation = await async_validate_api_key(self.hass, api_key)

        if validation.errors:
            return self.async_show_form(
                step_id="user", data_schema=API_KEY_SCHEMA, errors=validation.errors
            )

        self._flow_data = {CONF_API_KEY: api_key}
        return await self.async_step_by_coordinates()


class PurpleAirOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a PurpleAir options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}
        self.config_entry = config_entry

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a sensor."""
        if user_input is None:
            return self.async_show_form(
                step_id="add_sensor",
                data_schema=async_get_coordinates_schema(self.hass),
            )

        validation = await async_validate_coordinates(
            self.hass,
            self.config_entry.data[CONF_API_KEY],
            user_input[CONF_LATITUDE],
            user_input[CONF_LONGITUDE],
            user_input[CONF_DISTANCE],
        )

        if validation.errors:
            return self.async_show_form(
                step_id="add_sensor",
                data_schema=async_get_coordinates_schema(self.hass),
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_OPTIONS] = async_get_nearby_sensors_options(
            validation.data
        )

        return await self.async_step_choose_sensor()

    async def async_step_choose_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the selection of a sensor."""
        if user_input is None:
            options = self._flow_data.pop(CONF_NEARBY_SENSOR_OPTIONS)
            return self.async_show_form(
                step_id="choose_sensor",
                data_schema=async_get_nearby_sensors_schema(options),
            )

        sensor_index = int(user_input[CONF_SENSOR_INDEX])

        if sensor_index in self.config_entry.options[CONF_SENSOR_INDICES]:
            return self.async_abort(reason="already_configured")

        options = deepcopy({**self.config_entry.options})
        options[CONF_LAST_UPDATE_SENSOR_ADD] = True
        options[CONF_SENSOR_INDICES].append(sensor_index)
        return self.async_create_entry(title="", data=options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_sensor", "remove_sensor"],
        )

    async def async_step_remove_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a sensor."""
        if user_input is None:
            return self.async_show_form(
                step_id="remove_sensor",
                data_schema=async_get_remove_sensor_schema(
                    async_get_remove_sensor_options(self.hass, self.config_entry)
                ),
            )

        device_registry = dr.async_get(self.hass)
        device_entry = cast(
            dr.DeviceEntry, device_registry.async_get(user_input[CONF_SENSOR_DEVICE_ID])
        )

        removed_sensor_index = async_get_sensor_index(
            self.hass, self.config_entry, device_entry
        )

        # Remove the sensor's device from the device registry:
        device_registry.async_update_device(
            device_entry.id, remove_config_entry_id=self.config_entry.entry_id
        )

        # Untrack the sensor index in config entry options:
        new_entry_options = async_untrack_sensor_index(
            self.config_entry, removed_sensor_index
        )
        return self.async_create_entry(title="", data=new_entry_options)
