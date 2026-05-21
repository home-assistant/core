"""Schemas for the Google Travel Time integration."""

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_LANGUAGE, CONF_MODE
from homeassistant.helpers.selector import (
    ConfigEntrySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .const import (
    ALL_LANGUAGES,
    AVOID_OPTIONS,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DOMAIN,
    TIME_TYPES,
    TRAFFIC_MODELS,
    TRANSIT_PREFS,
    TRANSPORT_TYPES,
    TRAVEL_MODES_WITHOUT_TRANSIT,
    UNITS,
    UNITS_METRIC,
)

LANGUAGE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=sorted(ALL_LANGUAGES),
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_LANGUAGE,
    )
)

AVOID_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=AVOID_OPTIONS,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_AVOID,
    )
)

TRAFFIC_MODEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=TRAFFIC_MODELS,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_TRAFFIC_MODEL,
    )
)

TRANSIT_MODE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=TRANSPORT_TYPES,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_TRANSIT_MODE,
    )
)

TRANSIT_ROUTING_PREFERENCE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=TRANSIT_PREFS,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_TRANSIT_ROUTING_PREFERENCE,
    )
)

UNITS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=UNITS,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_UNITS,
    )
)

TIME_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=TIME_TYPES,
        sort=True,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_TIME_TYPE,
    )
)

_SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Required(CONF_ORIGIN): TextSelector(),
        vol.Required(CONF_DESTINATION): TextSelector(),
        vol.Optional(CONF_UNITS, default=UNITS_METRIC): UNITS_SELECTOR,
        vol.Optional(CONF_LANGUAGE): LANGUAGE_SELECTOR,
    }
)

SERVICE_GET_TRAVEL_TIMES_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_MODE, default="driving"): SelectSelector(
            SelectSelectorConfig(
                options=TRAVEL_MODES_WITHOUT_TRANSIT,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_MODE,
            )
        ),
        vol.Optional(CONF_AVOID): AVOID_SELECTOR,
        vol.Optional(CONF_TRAFFIC_MODEL): TRAFFIC_MODEL_SELECTOR,
        vol.Optional(CONF_DEPARTURE_TIME): TimeSelector(),
    }
)

SERVICE_GET_TRANSIT_TIMES_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_TRANSIT_MODE): TRANSIT_MODE_SELECTOR,
        vol.Optional(
            CONF_TRANSIT_ROUTING_PREFERENCE
        ): TRANSIT_ROUTING_PREFERENCE_SELECTOR,
        vol.Exclusive(CONF_DEPARTURE_TIME, "time"): TimeSelector(),
        vol.Exclusive(CONF_ARRIVAL_TIME, "time"): TimeSelector(),
    }
)
