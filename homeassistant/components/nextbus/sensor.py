"""NextBus sensor."""

from __future__ import annotations

import logging
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from .coordinator import NextBusDataUpdateCoordinator
from .util import maybe_first

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load values from configuration and initialize the platform."""
    _LOGGER.debug(config.data)
    entry_agency = config.data[CONF_AGENCY]
    entry_stop = config.data[CONF_STOP]
    coordinator_key = f"{entry_agency}-{entry_stop}"

    coordinator: NextBusDataUpdateCoordinator = hass.data[DOMAIN].get(coordinator_key)

    async_add_entities(
        (
            NextBusDepartureSensor(
                coordinator,
                cast(str, config.unique_id),
                config.data[CONF_AGENCY],
                config.data[CONF_ROUTE],
                config.data[CONF_STOP],
                config.data.get(CONF_NAME) or config.title,
            ),
        ),
    )


class NextBusDepartureSensor(
    CoordinatorEntity[NextBusDataUpdateCoordinator], SensorEntity
):
    """Sensor class that displays upcoming NextBus times.

    To function, this requires knowing the agency tag as well as the tags for
    both the route and the stop.

    This is possibly a little convoluted to provide as it requires making a
    request to the service to get these values. Perhaps it can be simplified in
    the future using fuzzy logic and matching.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "nextbus"

    def __init__(
        self,
        coordinator: NextBusDataUpdateCoordinator,
        unique_id: str,
        agency: str,
        route: str,
        stop: str,
        name: str,
    ) -> None:
        """Initialize sensor with all required config."""
        super().__init__(coordinator)
        self.agency = agency
        self.route = route
        self.stop = stop
        self._attr_extra_state_attributes: dict[str, str] = {
            "agency": agency,
            "route": route,
            "stop": stop,
        }
        self._attr_unique_id = unique_id
        self._attr_name = name

    def _log_debug(self, message, *args):
        """Log debug message with prefix."""
        msg = f"{self.agency}:{self.route}:{self.stop}:{message}"
        _LOGGER.debug(msg, *args)

    def _log_err(self, message, *args):
        """Log error message with prefix."""
        msg = f"{self.agency}:{self.route}:{self.stop}:{message}"
        _LOGGER.error(msg, *args)

    async def async_added_to_hass(self) -> None:
        """Read data from coordinator after adding to hass."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with new departures times."""
        results = self.coordinator.get_prediction_data(self.stop, self.route)

        self._log_debug("Predictions results: %s", results)

        if not results:
            self._log_err("Error getting predictions: %s", str(results))
            self._attr_native_value = None
            self._attr_extra_state_attributes.pop("upcoming", None)
            return

        # Set detailed attributes
        self._attr_extra_state_attributes.update(
            {
                "route": str(results["route"]["title"]),
                "stop": str(results["stop"]["name"]),
            }
        )

        # Chain all predictions together
        predictions = results["values"]

        # Short circuit if we don't have any actual bus predictions
        if not predictions:
            self._log_debug("No upcoming predictions available")
            self._attr_native_value = None
            self._attr_extra_state_attributes["upcoming"] = "No upcoming predictions"
        else:
            # Generate list of upcoming times
            self._attr_extra_state_attributes["upcoming"] = ", ".join(
                str(p["minutes"]) for p in predictions
            )

            latest_prediction = maybe_first(predictions)
            self._attr_native_value = utc_from_timestamp(
                latest_prediction["timestamp"] / 1000
            )

        self.async_write_ha_state()
