"""Schemas for the Google Travel Time integration."""

import probatio

from homeassistant.const import CONF_LANGUAGE, CONF_MODE, CommonServiceArgument
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
    CONF_AVOID,
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
    GoogleTravelTimeServiceArgument,
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

_SERVICE_BASE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        probatio.Required(GoogleTravelTimeServiceArgument.ORIGIN): TextSelector(),
        probatio.Required(GoogleTravelTimeServiceArgument.DESTINATION): TextSelector(),
        probatio.Optional(
            GoogleTravelTimeServiceArgument.UNITS, default=UNITS_METRIC
        ): UNITS_SELECTOR,
        probatio.Optional(GoogleTravelTimeServiceArgument.LANGUAGE): LANGUAGE_SELECTOR,
    }
)

SERVICE_GET_TRAVEL_TIMES_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Optional(
            GoogleTravelTimeServiceArgument.MODE, default="driving"
        ): SelectSelector(
            SelectSelectorConfig(
                options=TRAVEL_MODES_WITHOUT_TRANSIT,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_MODE,
            )
        ),
        probatio.Optional(GoogleTravelTimeServiceArgument.AVOID): AVOID_SELECTOR,
        probatio.Optional(
            GoogleTravelTimeServiceArgument.TRAFFIC_MODEL
        ): TRAFFIC_MODEL_SELECTOR,
        probatio.Optional(
            GoogleTravelTimeServiceArgument.DEPARTURE_TIME
        ): TimeSelector(),
    }
)

SERVICE_GET_TRANSIT_TIMES_SCHEMA = _SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Optional(
            GoogleTravelTimeServiceArgument.TRANSIT_MODE
        ): TRANSIT_MODE_SELECTOR,
        probatio.Optional(
            GoogleTravelTimeServiceArgument.TRANSIT_ROUTING_PREFERENCE
        ): TRANSIT_ROUTING_PREFERENCE_SELECTOR,
        probatio.Exclusive(
            GoogleTravelTimeServiceArgument.DEPARTURE_TIME, "time"
        ): TimeSelector(),
        probatio.Exclusive(
            GoogleTravelTimeServiceArgument.ARRIVAL_TIME, "time"
        ): TimeSelector(),
    }
)
