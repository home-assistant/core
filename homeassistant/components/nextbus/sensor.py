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
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_AGENCY, CONF_ROUTE, CONF_STOP, DOMAIN
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize nextbus import from config."""
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        breaks_in_ha_version="2024.4.0",
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "NextBus",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load values from configuration and initialize the platform."""
    client = NextBusClient(output_format="json")

    _LOGGER.debug(config.data)

    sensor = NextBusDepartureSensor(
        client,
        config.unique_id,
        config.data[CONF_AGENCY],
        config.data[CONF_ROUTE],
        config.data[CONF_STOP],
        config.data.get(CONF_NAME) or config.title,
    )

    async_add_entities((sensor,), True)


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

    def __init__(self, client, unique_id, agency, route, stop, name):
        """Initialize sensor with all required config."""
        self.agency = agency
        self.route = route
        self.stop = stop
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = unique_id
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
