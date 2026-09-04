"""Config flow for Forecast.Solar integration."""

from collections.abc import Mapping
import re
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
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
    CONF_TRACK_HOME_LOCATION,
    DEFAULT_AZIMUTH,
    DEFAULT_DAMPING,
    DEFAULT_DECLINATION,
    DEFAULT_MODULES_POWER,
    DOMAIN,
    MAX_PLANES,
    SUBENTRY_TYPE_PLANE,
)

RE_API_KEY = re.compile(r"^[a-zA-Z0-9]{16}$")

_ANGLE_UNITS: frozenset[str] = frozenset({"°", "degrees", "deg", "degree"})


def _get_angle_sensor_ids(hass: HomeAssistant) -> list[str]:
    """Get entity IDs of sensors that report angle units."""
    return [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if (state := hass.states.get(entity_id)) is not None
        and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in _ANGLE_UNITS
    ]


def _location_data(
    user_input: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Resolve location data from a submitted form, returning data and errors."""
    if user_input[CONF_TRACK_HOME_LOCATION]:
        return {}, {}
    if CONF_LATITUDE in user_input and CONF_LONGITUDE in user_input:
        return {
            CONF_LATITUDE: user_input[CONF_LATITUDE],
            CONF_LONGITUDE: user_input[CONF_LONGITUDE],
        }, {}
    return {}, {"base": "location_required"}


_LOCATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TRACK_HOME_LOCATION, default=True): bool,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
    }
)


def _plane_data(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Extract a plane's stored fields from a submitted plane form."""
    return {
        key: user_input[key]
        for key in (
            CONF_DECLINATION,
            CONF_AZIMUTH,
            CONF_MODULES_POWER,
            CONF_DECLINATION_SENSOR,
            CONF_AZIMUTH_SENSOR,
        )
        if key in user_input
    }


def _plane_title(data: Mapping[str, Any], hass: HomeAssistant) -> str:
    """Build a plane subentry title from its resolved azimuth/declination/power."""
    if entity_id := data.get(CONF_DECLINATION_SENSOR):
        state = hass.states.get(entity_id)
        declination_label = state.name if state else entity_id
    else:
        declination_label = f"{data[CONF_DECLINATION]}°"

    if entity_id := data.get(CONF_AZIMUTH_SENSOR):
        state = hass.states.get(entity_id)
        azimuth_label = state.name if state else entity_id
    else:
        azimuth_label = f"{data[CONF_AZIMUTH]}°"

    return f"{declination_label} / {azimuth_label} / {data[CONF_MODULES_POWER]}W"


def _plane_schema(hass: HomeAssistant) -> vol.Schema:
    """Build the plane form schema, offering sensor fields only if any angle sensors exist."""
    angle_sensors = _get_angle_sensor_ids(hass)
    angle_sensor_selector = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=angle_sensors, mode=selector.SelectSelectorMode.DROPDOWN
        )
    )

    schema: dict[Any, Any] = {
        vol.Required(CONF_DECLINATION): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=1, mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Coerce(int),
        ),
    }
    if angle_sensors:
        schema[vol.Optional(CONF_DECLINATION_SENSOR)] = angle_sensor_selector

    schema[vol.Required(CONF_AZIMUTH)] = vol.All(
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=360, step=1, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Coerce(int),
    )
    if angle_sensors:
        schema[vol.Optional(CONF_AZIMUTH_SENSOR)] = angle_sensor_selector

    schema[vol.Required(CONF_MODULES_POWER)] = vol.All(
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, step=1, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Coerce(int),
    )
    return vol.Schema(schema)


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

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location_data, errors = _location_data(user_input)

            if not errors:
                plane_data = _plane_data(user_input)
                return self.async_create_entry(
                    title="",
                    data=location_data,
                    subentries=[
                        {
                            "subentry_type": SUBENTRY_TYPE_PLANE,
                            "data": plane_data,
                            "title": _plane_title(plane_data, self.hass),
                            "unique_id": None,
                        },
                    ],
                )

        schema = _LOCATION_SCHEMA.extend(_plane_schema(self.hass).schema)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_DECLINATION: DEFAULT_DECLINATION,
                    CONF_AZIMUTH: DEFAULT_AZIMUTH,
                    CONF_MODULES_POWER: DEFAULT_MODULES_POWER,
                },
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry's location."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            location_data, errors = _location_data(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=location_data)

        suggested_values = user_input or {
            CONF_TRACK_HOME_LOCATION: not entry.data,
            CONF_LATITUDE: entry.data.get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: entry.data.get(CONF_LONGITUDE, self.hass.config.longitude),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _LOCATION_SCHEMA, suggested_values
            ),
            errors=errors,
        )


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
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY,
                        default=suggested_api_key,
                    )
                    if planes_count > 1
                    else vol.Optional(
                        CONF_API_KEY,
                        description={"suggested_value": suggested_api_key},
                    ): str,
                    vol.Optional(
                        CONF_DAMPING_MORNING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_MORNING, DEFAULT_DAMPING
                        ),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1,
                                step=0.01,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        vol.Coerce(float),
                    ),
                    vol.Optional(
                        CONF_DAMPING_EVENING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_EVENING, DEFAULT_DAMPING
                        ),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=0,
                                max=1,
                                step=0.01,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        vol.Coerce(float),
                    ),
                    vol.Optional(
                        CONF_INVERTER_SIZE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_INVERTER_SIZE
                            )
                        },
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            errors=errors,
        )


class PlaneSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for adding/editing a plane."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step to add a new plane."""
        entry = self._get_entry()
        planes_count = len(entry.get_subentries_of_type(SUBENTRY_TYPE_PLANE))
        if planes_count >= MAX_PLANES:
            return self.async_abort(reason="max_planes")
        if planes_count >= 1 and not entry.options.get(CONF_API_KEY):
            return self.async_abort(reason="api_key_required")

        if user_input is not None:
            return self.async_create_entry(
                title=_plane_title(user_input, self.hass), data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _plane_schema(self.hass),
                {
                    CONF_DECLINATION: DEFAULT_DECLINATION,
                    CONF_AZIMUTH: DEFAULT_AZIMUTH,
                    CONF_MODULES_POWER: DEFAULT_MODULES_POWER,
                },
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an existing plane."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            entry = self._get_entry()
            title = _plane_title(user_input, self.hass)
            if (
                self._async_update(entry, subentry, data=user_input, title=title)
                and not entry.update_listeners
            ):
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _plane_schema(self.hass), subentry.data
            ),
        )
