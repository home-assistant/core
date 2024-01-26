"""Support for tracking the proximity of a device."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_ZONE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_TO,
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
    for friendly_name, proximity_config in config[DOMAIN].items():
        _LOGGER.debug("setup %s with config:%s", friendly_name, proximity_config)

        coordinator = ProximityDataUpdateCoordinator(
            hass, friendly_name, proximity_config
        )

        async_track_state_change(
            hass,
            proximity_config[CONF_DEVICES],
            coordinator.async_check_proximity_state_change,
        )

        await coordinator.async_refresh()
        hass.data[DOMAIN][friendly_name] = coordinator

        proximity = Proximity(hass, friendly_name, coordinator)
        await proximity.async_added_to_hass()
        proximity.async_write_ha_state()

        await async_load_platform(
            hass,
            "sensor",
            DOMAIN,
            {CONF_NAME: friendly_name, **proximity_config},
            config,
        )

        # deprecate proximity entity - can be removed in 2024.8
        used_in = automations_with_entity(hass, f"{DOMAIN}.{friendly_name}")
        used_in += scripts_with_entity(hass, f"{DOMAIN}.{friendly_name}")
        if used_in:
            async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_proximity_entity_{friendly_name}",
                breaks_in_ha_version="2024.8.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_proximity_entity",
                translation_placeholders={
                    "entity": f"{DOMAIN}.{friendly_name}",
                    "used_in": "\n- ".join([f"`{x}`" for x in used_in]),
                },
            )

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
        return self.coordinator.data.proximity[ATTR_DIST_TO]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            ATTR_DIR_OF_TRAVEL: str(
                self.coordinator.data.proximity[ATTR_DIR_OF_TRAVEL]
            ),
            ATTR_NEAREST: str(self.coordinator.data.proximity[ATTR_NEAREST]),
        }
