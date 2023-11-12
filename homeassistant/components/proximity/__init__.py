"""Support for tracking the proximity of a device."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_UNIT_OF_MEASUREMENT, CONF_ZONE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_NEAREST,
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    DEFAULT_PROXIMITY_ZONE,
    DEFAULT_TOLERANCE,
    DOMAIN,
    UNITS,
)
from .coordinator import ProximityDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ZONE, default=DEFAULT_PROXIMITY_ZONE): cv.string,
        vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_IGNORED_ZONES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(cv.string, vol.In(UNITS)),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ZONE_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Get the zones and offsets from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})
    for zone, proximity_config in config[DOMAIN].items():
        _LOGGER.debug("setup %s with config:%s", zone, proximity_config)

        coordinator = ProximityDataUpdateCoordinator(hass, zone, proximity_config)

        async_track_state_change(
            hass,
            proximity_config[CONF_DEVICES],
            coordinator.async_check_proximity_state_change,
        )

        await coordinator.async_refresh()
        hass.data[DOMAIN][zone] = coordinator

        proximity = Proximity(hass, zone, coordinator)
        await proximity.async_added_to_hass()
        proximity.async_write_ha_state()

    return True


class Proximity(CoordinatorEntity[ProximityDataUpdateCoordinator]):
    """Representation of a Proximity."""

    # This entity is legacy and does not have a platform.
    # We can't fix this easily without breaking changes.
    _no_platform_reported = True

    def __init__(
        self,
        hass: HomeAssistant,
        friendly_name: str,
        coordinator: ProximityDataUpdateCoordinator,
    ) -> None:
        """Initialize the proximity."""
        super().__init__(coordinator)
        self.hass = hass
        self.entity_id = f"{DOMAIN}.{friendly_name}"

        self._attr_name = friendly_name
        self._attr_unit_of_measurement = self.coordinator.unit_of_measurement

    @property
    def state(self) -> str | int | float:
        """Return the state."""
        return self.coordinator.data["dist_to_zone"]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            ATTR_DIR_OF_TRAVEL: str(self.coordinator.data["dir_of_travel"]),
            ATTR_NEAREST: str(self.coordinator.data["nearest"]),
        }
