"""CityBus sensor."""

import logging
from datetime import datetime

from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utc_from_timestamp

from .const import CONF_ROUTE, CONF_DIRECTION, CONF_STOP, DOMAIN
from .coordinator import CityBusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load values from configuration and initialize the platform."""
    _LOGGER.debug(config.data)
    entry_route = config.data[CONF_ROUTE]
    entry_direction = config.data[CONF_DIRECTION]
    entry_stop = config.data[CONF_STOP]
    coordinator_key = f"{entry_route}-{entry_direction}-{entry_stop}"

    coordinator: CityBusDataUpdateCoordinator = hass.data[DOMAIN].get(coordinator_key)

    async_add_entities(
        (
            CityBusNextBusSensor(
                coordinator,
                cast(str, config.unique_id),
                config.data[CONF_ROUTE],
                config.data[CONF_DIRECTION],
                config.data[CONF_STOP],
                config.data.get(CONF_NAME) or config.title,
            ),
        ),
    )

class CityBusNextBusSensor(CoordinatorEntity[CityBusDataUpdateCoordinator], SensorEntity):
    """Sensor class that displays upcoming CityBus times.
    
    To function, this requires knowing the key or code for the route, direction, and stop."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "citybus"

    def __init__(
        self,
        coordinator: CityBusDataUpdateCoordinator,
        unique_id: str,
        route_key: str,
        direction_key: str,
        stop_code: str,
        name: str,
    ) -> None:
        """Initialize sensor with all required config."""
        super().__init__(coordinator)
        self.route_key = route_key
        self.direction_key = direction_key
        self.stop_code = stop_code
        self._attr_extra_state_attributes: dict[str, str] = {
            "route_key": route_key,
            "direction_key": direction_key,
            "stop_code": stop_code,
        }
        self._attr_unique_id = unique_id
        self._attr_name = name
    
    def _log_debug(self, message, *args):
        """Log debug message with prefix."""
        msg = f"{self.route_key}:{self.direction_key}:{self.stop_code}:{message}"
        _LOGGER.debug(msg, *args)
    
    def _log_err(self, message, *args):
        """Log error message with prefix."""
        msg = f"{self.route_key}:{self.direction_key}:{self.stop_code}:{message}"
        _LOGGER.error(msg, *args)
    
    async def async_added_to_hass(self) -> None:
        """Read data from coordinator after adding to hass."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with new estimate times."""
        results = self.coordinator.get_estimate_data(self.route_key, self.direction_key, self.stop_code)

        self._log_debug("Estimate results: %s", results)

        if not results:
            self._log_err("Error getting estimates: %s", str(results))
            self._attr_native_value = None
            return
        


        estimates = results

        # Short circuit if there are no estimates available
        if not estimates:
            self._log_debug("No upcoming buses available")
            self._attr_native_value = None
            self._attr_extra_state_attributes["upcoming"] = "No upcoming estimates"
        else:
            self._attr_extra_state_attributes["upcoming"] = ", ".join(
                str(e["estimatedDepartTimeUtc"]) for e in estimates
            )

            first_bus = estimates[0]
            self._attr_native_value = datetime.fromisoformat(first_bus["estimatedDepartTimeUtc"])
        
        self.async_write_ha_state()
