"""PurpleAir subentry flow."""

from __future__ import annotations

from typing import Any, Final

from aiopurpleair import API
from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.errors import (
    InvalidApiKeyError,
    InvalidRequestError,
    NotFoundError,
    PurpleAirError,
    RequestError,
)
from aiopurpleair.models.sensors import GetSensorsResponse, SensorModel
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BASE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    UnitOfLength,
)
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_ADD_MAP_LOCATION,
    CONF_ADD_OPTIONS,
    CONF_ADD_SENSOR_INDEX,
    CONF_ALREADY_CONFIGURED,
    CONF_INVALID_API_KEY,
    CONF_NO_SENSOR_FOUND,
    CONF_NO_SENSORS_FOUND,
    CONF_SELECT_SENSOR,
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    CONF_UNKNOWN,
    DOMAIN,
    LOGGER,
    SENSOR_FIELDS_ALL,
)

DEFAULT_RADIUS: Final[int] = 2000
LIMIT_RESULTS: Final[int] = 25
SENSOR_FIELDS_NEARBY: Final[list[str]] = ["name", "longitude", "latitude"]

CONF_NEARBY_SENSOR_LIST: Final[str] = "nearby_sensor_list"


class PurpleAirSubentryFlow(ConfigSubentryFlow):
    """Handle subentry flow."""

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}
        self._errors: dict[str, Any] = {}

    # TODO: Getting the parent seems generally useful and could be in the base sub entry class for general use? # pylint: disable=fixme
    # Copy pasted this logic from the sub entry proposal thread where others had the same questions and this pattern was recommended.
    # Could not repro the None error logic so test coverage here is missing.
    def _get_parent_config_entry(self) -> ConfigEntry:
        if self.hass is None or self.handler is None:
            raise ValueError("Parent ConfigEntry not available")
        return self.hass.config_entries.async_get_known_entry(self.handler[0])

    def _get_title(self, sensor: SensorModel) -> str:
        """Get sensor title."""
        return f"{sensor.name} ({sensor.sensor_index})"

    async def _async_validate_coordinates(self) -> bool:
        """Validate coordinates."""
        self._errors = {}

        api = API(
            self._flow_data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(self.hass),
        )
        try:
            nearby_sensor_list: list[
                NearbySensorResult
            ] = await api.sensors.async_get_nearby_sensors(
                SENSOR_FIELDS_NEARBY,
                self._flow_data[CONF_LATITUDE],
                self._flow_data[CONF_LONGITUDE],
                DistanceConverter.convert(
                    self._flow_data[CONF_RADIUS],
                    UnitOfLength.METERS,
                    UnitOfLength.KILOMETERS,
                ),
                limit_results=LIMIT_RESULTS,
            )
            LOGGER.debug("NearbySensorResult: %s", nearby_sensor_list)
        except InvalidApiKeyError as err:
            LOGGER.exception("InvalidApiKeyError exception: %s", err)
            self._errors[CONF_BASE] = CONF_INVALID_API_KEY
            return False
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.exception("PurpleAirError exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False

        if not nearby_sensor_list or len(nearby_sensor_list) == 0:
            self._errors[CONF_LOCATION] = CONF_NO_SENSORS_FOUND
            return False

        self._flow_data[CONF_NEARBY_SENSOR_LIST] = nearby_sensor_list
        return True

    async def _async_validate_sensor(self) -> bool:
        """Validate sensor."""
        self._errors = {}

        sensor_index: int = self._flow_data[CONF_SENSOR_INDEX]
        index_list: list[int] = [sensor_index]

        read_key: str | None = self._flow_data[CONF_SENSOR_READ_KEY]
        read_key_list: list[str] | None = None
        if read_key is not None and type(read_key) is str and len(read_key) > 0:
            read_key_list = [read_key]

        api = API(
            self._flow_data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(self.hass),
        )
        try:
            sensors_response: GetSensorsResponse = await api.sensors.async_get_sensors(
                SENSOR_FIELDS_ALL,
                sensor_indices=index_list,
                read_keys=read_key_list,
            )
            LOGGER.debug("GetSensorsResponse: %s", sensors_response)
        except InvalidApiKeyError as err:
            LOGGER.exception("InvalidApiKeyError exception: %s", err)
            self._errors[CONF_BASE] = CONF_INVALID_API_KEY
            return False
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.exception("PurpleAirError exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False

        if (
            not sensors_response
            or not sensors_response.data
            or sensors_response.data.get(sensor_index) is None
            or sensors_response.data[sensor_index] is None
            or sensors_response.data[sensor_index].sensor_index != sensor_index
        ):
            self._errors[CONF_SENSOR_INDEX] = CONF_NO_SENSOR_FOUND
            return False

        # TODO: _raise_if_subentry_unique_id_exists() only tests uniqueness for this config entry, but sensors need to be unique globally. # pylint: disable=fixme
        # Could be useful if the base sub entry class supports an options for globally unique testing not just testing for the current config entry.
        global_index_list: list[int] = [
            int(subentry.data[CONF_SENSOR_INDEX])
            for config_entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
            for subentry in config_entry.subentries.values()
        ]
        if sensor_index in global_index_list:
            self._errors[CONF_SENSOR_INDEX] = CONF_ALREADY_CONFIGURED
            return False

        self._flow_data[CONF_SENSOR] = sensors_response.data[sensor_index]
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle user initialization flow."""
        self._flow_data[CONF_API_KEY] = self._get_parent_config_entry().data[
            CONF_API_KEY
        ]
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
            self._flow_data[CONF_RADIUS] = float(DEFAULT_RADIUS)

        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ADD_MAP_LOCATION,
                data_schema=self.map_location_schema,
            )

        self._flow_data[CONF_LATITUDE] = float(user_input[CONF_LOCATION][CONF_LATITUDE])
        self._flow_data[CONF_LONGITUDE] = float(
            user_input[CONF_LOCATION][CONF_LONGITUDE]
        )
        self._flow_data[CONF_RADIUS] = float(user_input[CONF_LOCATION][CONF_RADIUS])
        if not await self._async_validate_coordinates():
            return self.async_show_form(
                step_id=CONF_ADD_MAP_LOCATION,
                data_schema=self.map_location_schema,
                errors=self._errors,
            )

        assert self._flow_data.get(CONF_NEARBY_SENSOR_LIST) is not None

        return await self.async_step_select_sensor()

    @property
    def select_sensor_schema(self) -> vol.Schema:
        """Selection list schema."""
        nearby_sensor_list: list[NearbySensorResult] = self._flow_data[
            CONF_NEARBY_SENSOR_LIST
        ]
        return vol.Schema(
            {
                vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=str(result.sensor.sensor_index),
                                label=self._get_title(result.sensor),
                            )
                            for result in nearby_sensor_list
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

        self._flow_data[CONF_SENSOR_INDEX] = int(user_input[CONF_SENSOR_INDEX])
        self._flow_data[CONF_SENSOR_READ_KEY] = None
        if not await self._async_validate_sensor():
            return self.async_show_form(
                step_id=CONF_SELECT_SENSOR,
                data_schema=self.select_sensor_schema,
                errors=self._errors,
            )

        sensor: SensorModel = self._flow_data[CONF_SENSOR]
        assert sensor is not None

        return self.async_create_entry(
            title=self._get_title(sensor),
            data={CONF_SENSOR_INDEX: sensor.sensor_index},
            unique_id=str(sensor.sensor_index),
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
        if not await self._async_validate_sensor():
            return self.async_show_form(
                step_id=CONF_ADD_SENSOR_INDEX,
                data_schema=self.sensor_index_schema,
                errors=self._errors,
            )

        sensor: SensorModel = self._flow_data[CONF_SENSOR]
        assert sensor is not None

        data: dict[str, Any] = {CONF_SENSOR_INDEX: sensor.sensor_index}
        read_key: str | None = self._flow_data[CONF_SENSOR_READ_KEY]
        if read_key is not None and type(read_key) is str and len(read_key) > 0:
            data[CONF_SENSOR_READ_KEY] = read_key

        return self.async_create_entry(
            title=self._get_title(sensor),
            data=data,
            unique_id=str(sensor.sensor_index),
        )
