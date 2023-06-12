"""NextBus sensor."""
from __future__ import annotations

from itertools import chain
import logging

from py_nextbus import NextBusClient
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_AGENCY, CONF_ROUTE, CONF_STOP
from .util import listify, maybe_first

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AGENCY): cv.string,
        vol.Required(CONF_ROUTE): cv.string,
        vol.Required(CONF_STOP): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


def validate_value(value_name, value, value_list):
    """Validate tag value is in the list of items and logs error if not."""
    valid_values = {v["tag"]: v["title"] for v in value_list}
    if value not in valid_values:
        _LOGGER.error(
            "Invalid %s tag `%s`. Please use one of the following: %s",
            value_name,
            value,
            ", ".join(f"{title}: {tag}" for tag, title in valid_values.items()),
        )
        return False

    return True


def validate_tags(client, agency, route, stop):
    """Validate provided tags."""
    # Validate agencies
    if not validate_value("agency", agency, client.get_agency_list()["agency"]):
        return False

    # Validate the route
    if not validate_value("route", route, client.get_route_list(agency)["route"]):
        return False

    # Validate the stop
    route_config = client.get_route_config(route, agency)["route"]
    if not validate_value("stop", stop, route_config["stop"]):
        return False

    return True


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Load values from configuration and initialize the platform."""
    agency = config[CONF_AGENCY]
    route = config[CONF_ROUTE]
    stop = config[CONF_STOP]
    name = config.get(CONF_NAME)

    client = NextBusClient(output_format="json")

    # Ensures that the tags provided are valid, also logs out valid values
    if not validate_tags(client, agency, route, stop):
        _LOGGER.error("Invalid config value(s)")
        return

    add_entities([NextBusDepartureSensor(client, agency, route, stop, name)], True)


class NextBusDepartureSensor(SensorEntity):
    """Sensor class that displays upcoming NextBus times.

    To function, this requires knowing the agency tag as well as the tags for
    both the route and the stop.

    This is possibly a little convoluted to provide as it requires making a
    request to the service to get these values. Perhaps it can be simplified in
    the future using fuzzy logic and matching.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus"

    def __init__(self, client, agency, route, stop, name=None):
        """Initialize sensor with all required config."""
        self.agency = agency
        self.route = route
        self.stop = stop
        self._attr_extra_state_attributes = {}

        # Maybe pull a more user friendly name from the API here
        self._attr_name = f"{agency} {route}"
        if name:
            self._attr_name = name

        self._client = client

    def _log_debug(self, message, *args):
        """Log debug message with prefix."""
        _LOGGER.debug(":".join((self.agency, self.route, self.stop, message)), *args)

    def update(self) -> None:
        """Update sensor with new departures times."""
        # Note: using Multi because there is a bug with the single stop impl
        results = self._client.get_predictions_for_multi_stops(
            [{"stop_tag": self.stop, "route_tag": self.route}], self.agency
        )

        self._log_debug("Predictions results: %s", results)
        self._attr_attribution = results.get("copyright")

        if "Error" in results:
            self._log_debug("Could not get predictions: %s", results)

        if not results.get("predictions"):
            self._log_debug("No predictions available")
            self._attr_native_value = None
            # Remove attributes that may now be outdated
            self._attr_extra_state_attributes.pop("upcoming", None)
            return

        results = results["predictions"]

        # Set detailed attributes
        self._attr_extra_state_attributes.update(
            {
                "agency": results.get("agencyTitle"),
                "route": results.get("routeTitle"),
                "stop": results.get("stopTitle"),
            }
        )

        # List all messages in the attributes
        messages = listify(results.get("message", []))
        self._log_debug("Messages: %s", messages)
        self._attr_extra_state_attributes["message"] = " -- ".join(
            message.get("text", "") for message in messages
        )

        # List out all directions in the attributes
        directions = listify(results.get("direction", []))
        self._attr_extra_state_attributes["direction"] = ", ".join(
            direction.get("title", "") for direction in directions
        )

        # Chain all predictions together
        predictions = list(
            chain(
                *(listify(direction.get("prediction", [])) for direction in directions)
            )
        )

        # Short circuit if we don't have any actual bus predictions
        if not predictions:
            self._log_debug("No upcoming predictions available")
            self._attr_native_value = None
            self._attr_extra_state_attributes["upcoming"] = "No upcoming predictions"
            return

        # Generate list of upcoming times
        self._attr_extra_state_attributes["upcoming"] = ", ".join(
            sorted((p["minutes"] for p in predictions), key=int)
        )

        latest_prediction = maybe_first(predictions)
        self._attr_native_value = utc_from_timestamp(
            int(latest_prediction["epochTime"]) / 1000
        )
