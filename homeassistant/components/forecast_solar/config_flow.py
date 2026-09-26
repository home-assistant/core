"""Config flow for Forecast.Solar integration."""

from collections.abc import Mapping
import re
from typing import Any, override

import probatio

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DEFAULT_AZIMUTH,
    DEFAULT_DAMPING,
    DEFAULT_DECLINATION,
    DEFAULT_MODULES_POWER,
    DOMAIN,
    MAX_PLANES,
    SUBENTRY_TYPE_PLANE,
)
from .plane import SensorUpdateFailed, plane_title, sensor_angle

RE_API_KEY = re.compile(r"^[a-zA-Z0-9]{16}$")

# Flow-only choices; the stored data records them by which keys are present.
_LOCATION = "location"
_DECLINATION_SOURCE = "declination_source"
_AZIMUTH_SOURCE = "azimuth_source"
_HOME = "home"
_FIXED = "fixed"
_SENSOR = "sensor"


def _choice(translation_key: str, options: list[str]) -> selector.SelectSelector:
    """Build a radio group of translated options."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.LIST,
            translation_key=translation_key,
        )
    )


_SOURCES_SCHEMA = probatio.Schema(
    {
        probatio.Required(_DECLINATION_SOURCE, default=_FIXED): _choice(
            "declination_source", [_FIXED, _SENSOR]
        ),
        probatio.Required(_AZIMUTH_SOURCE, default=_FIXED): _choice(
            "azimuth_source", [_FIXED, _SENSOR]
        ),
    }
)

_SETUP_CHOICES_SCHEMA = probatio.Schema(
    {probatio.Required(_LOCATION, default=_FIXED): _choice("location", [_FIXED, _HOME])}
).extend(_SOURCES_SCHEMA.schema)

_COORDINATES_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_LATITUDE): cv.latitude,
        probatio.Required(CONF_LONGITUDE): cv.longitude,
    }
)

_ANGLE_SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
)

_DECLINATION_FIELDS: dict[str, tuple[str, Any]] = {
    _FIXED: (
        CONF_DECLINATION,
        probatio.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                ),
            ),
            probatio.Coerce(int),
        ),
    ),
    _SENSOR: (CONF_DECLINATION_SENSOR, _ANGLE_SENSOR_SELECTOR),
}

_AZIMUTH_FIELDS: dict[str, tuple[str, Any]] = {
    _FIXED: (
        CONF_AZIMUTH,
        probatio.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1, mode=selector.NumberSelectorMode.BOX
                ),
            ),
            probatio.Coerce(int),
        ),
    ),
    _SENSOR: (CONF_AZIMUTH_SENSOR, _ANGLE_SENSOR_SELECTOR),
}

_PLANE_DEFAULTS = {
    CONF_DECLINATION: DEFAULT_DECLINATION,
    CONF_AZIMUTH: DEFAULT_AZIMUTH,
    CONF_MODULES_POWER: DEFAULT_MODULES_POWER,
}


def _plane_schema(sources: Mapping[str, str]) -> probatio.Schema:
    """Build the plane form, with only the field each angle's source needs."""
    declination_key, declination_validator = _DECLINATION_FIELDS[
        sources[_DECLINATION_SOURCE]
    ]
    azimuth_key, azimuth_validator = _AZIMUTH_FIELDS[sources[_AZIMUTH_SOURCE]]
    return probatio.Schema(
        {
            probatio.Required(declination_key): declination_validator,
            probatio.Required(azimuth_key): azimuth_validator,
            probatio.Required(CONF_MODULES_POWER): probatio.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, step=1, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                probatio.Coerce(int),
            ),
        }
    )


def _sensor_errors(
    hass: HomeAssistant, plane_data: Mapping[str, Any]
) -> dict[str, str]:
    """Return a form error per selected sensor that can't be read as an angle."""
    errors: dict[str, str] = {}
    for sensor_key in (CONF_DECLINATION_SENSOR, CONF_AZIMUTH_SENSOR):
        if (entity_id := plane_data.get(sensor_key)) is None:
            continue
        # A sensor that is merely unavailable is accepted; it is read on every update.
        state = hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        try:
            sensor_angle(hass, entity_id, sensor_key)
        except SensorUpdateFailed:
            errors[sensor_key] = "sensor_unusable"
    return errors


def _sources(data: Mapping[str, Any]) -> dict[str, str]:
    """Return the angle sources a stored plane uses."""
    return {
        _DECLINATION_SOURCE: _SENSOR if CONF_DECLINATION_SENSOR in data else _FIXED,
        _AZIMUTH_SOURCE: _SENSOR if CONF_AZIMUTH_SENSOR in data else _FIXED,
    }


def _plane_data(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Extract a plane's stored fields from a submitted plane form."""
    return {
        key: user_input[key]
        for key in (
            CONF_DECLINATION,
            CONF_DECLINATION_SENSOR,
            CONF_AZIMUTH,
            CONF_AZIMUTH_SENSOR,
            CONF_MODULES_POWER,
        )
        if key in user_input
    }


class ForecastSolarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast.Solar."""

    VERSION = 3

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler()

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_PLANE: PlaneSubentryFlowHandler}

    _choices: dict[str, str]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the location and where each plane angle comes from."""
        if user_input is not None:
            self._choices = user_input
            return await self.async_step_plane()

        return self.async_show_form(step_id="user", data_schema=_SETUP_CHOICES_SCHEMA)

    async def async_step_plane(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask only for the values the chosen sources need."""
        fixed_location = self._choices[_LOCATION] == _FIXED
        errors: dict[str, str] = {}

        if user_input is not None:
            plane_data = _plane_data(user_input)
            if not (errors := _sensor_errors(self.hass, plane_data)):
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                    }
                    if fixed_location
                    else {},
                    subentries=[
                        {
                            "subentry_type": SUBENTRY_TYPE_PLANE,
                            "data": plane_data,
                            "title": plane_title(self.hass, plane_data),
                            "unique_id": None,
                        },
                    ],
                )

        schema = _plane_schema(self._choices)
        suggested_values: dict[str, Any] = dict(_PLANE_DEFAULTS)
        if fixed_location:
            schema = _COORDINATES_SCHEMA.extend(schema.schema)
            suggested_values |= {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            }
        return self.async_show_form(
            step_id="plane",
            data_schema=self.add_suggested_values_to_schema(
                schema, suggested_values | (user_input or {})
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry's location."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["reconfigure_fixed_location", "reconfigure_home_location"],
        )

    async def async_step_reconfigure_home_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an entry to track Home Assistant's location."""
        return self._async_update_location({})

    async def async_step_reconfigure_fixed_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an entry to use fixed coordinates."""
        if user_input is not None:
            return self._async_update_location(
                {
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                }
            )

        entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure_fixed_location",
            data_schema=self.add_suggested_values_to_schema(
                _COORDINATES_SCHEMA,
                {
                    CONF_LATITUDE: entry.data.get(
                        CONF_LATITUDE, self.hass.config.latitude
                    ),
                    CONF_LONGITUDE: entry.data.get(
                        CONF_LONGITUDE, self.hass.config.longitude
                    ),
                },
            ),
        )

    def _async_update_location(self, location_data: dict[str, Any]) -> ConfigFlowResult:
        """Store the entry's new location, letting its update listener reload it."""
        entry = self._get_reconfigure_entry()
        if (
            self.hass.config_entries.async_update_entry(entry, data=location_data)
            and not entry.update_listeners
        ):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")


class ForecastSolarOptionFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        planes_count = len(
            self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE)
        )

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY)
            if planes_count > 1 and not api_key:
                errors[CONF_API_KEY] = "api_key_required"
            elif api_key and RE_API_KEY.match(api_key) is None:
                errors[CONF_API_KEY] = "invalid_api_key"
            else:
                return self.async_create_entry(
                    title="", data=user_input | {CONF_API_KEY: api_key or None}
                )

        suggested_api_key = self.config_entry.options.get(CONF_API_KEY, "")

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_API_KEY,
                        default=suggested_api_key,
                    )
                    if planes_count > 1
                    else probatio.Optional(
                        CONF_API_KEY,
                        description={"suggested_value": suggested_api_key},
                    ): str,
                    probatio.Optional(
                        CONF_DAMPING_MORNING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_MORNING, DEFAULT_DAMPING
                        ),
                    ): probatio.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1,
                                step=0.01,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        probatio.Coerce(float),
                    ),
                    probatio.Optional(
                        CONF_DAMPING_EVENING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_EVENING, DEFAULT_DAMPING
                        ),
                    ): probatio.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1,
                                step=0.01,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        probatio.Coerce(float),
                    ),
                    probatio.Optional(
                        CONF_INVERTER_SIZE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_INVERTER_SIZE
                            )
                        },
                    ): probatio.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        probatio.Coerce(int),
                    ),
                }
            ),
            errors=errors,
        )


class PlaneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding/editing a plane."""

    _sources: dict[str, str]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose where the new plane's angles come from."""
        entry = self._get_entry()
        planes_count = len(entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE))
        if planes_count >= MAX_PLANES:
            return self.async_abort(reason="max_planes")
        if planes_count >= 1 and not entry.options.get(CONF_API_KEY):
            return self.async_abort(reason="api_key_required")

        if user_input is not None:
            self._sources = user_input
            return await self.async_step_plane()

        return self.async_show_form(step_id="user", data_schema=_SOURCES_SCHEMA)

    async def async_step_plane(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask only for the values the chosen sources need."""
        errors: dict[str, str] = {}

        if user_input is not None:
            plane_data = _plane_data(user_input)
            if not (errors := _sensor_errors(self.hass, plane_data)):
                return self.async_create_entry(
                    title=plane_title(self.hass, plane_data), data=plane_data
                )

        return self.async_show_form(
            step_id="plane",
            data_schema=self.add_suggested_values_to_schema(
                _plane_schema(self._sources), _PLANE_DEFAULTS | (user_input or {})
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose where an existing plane's angles come from."""
        if user_input is not None:
            self._sources = user_input
            return await self.async_step_reconfigure_plane()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _SOURCES_SCHEMA, _sources(self._get_reconfigure_subentry().data)
            ),
        )

    async def async_step_reconfigure_plane(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit the values the chosen sources need."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            plane_data = _plane_data(user_input)
            if not (errors := _sensor_errors(self.hass, plane_data)):
                entry = self._get_entry()
                title = plane_title(self.hass, plane_data)
                if (
                    self._async_update(entry, subentry, data=plane_data, title=title)
                    and not entry.update_listeners
                ):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_plane",
            data_schema=self.add_suggested_values_to_schema(
                _plane_schema(self._sources),
                {**_PLANE_DEFAULTS, **subentry.data, **(user_input or {})},
            ),
            errors=errors,
        )
