"""Support for tracking the proximity of a device."""
from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_ZONE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_TO,
    ATTR_NEAREST,
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DEFAULT_PROXIMITY_ZONE,
    DEFAULT_TOLERANCE,
    DOMAIN,
    UNITS,
)
from .coordinator import ProximityDataUpdateCoordinator
from .helpers import entity_used_in

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
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: cv.schema_with_slug_keys(ZONE_SCHEMA)},
    ),
    extra=vol.ALLOW_EXTRA,
)


async def _async_setup_legacy(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: ProximityDataUpdateCoordinator
) -> None:
    """Legacy proximity entity handling, can be removed in 2024.8."""
    friendly_name = entry.data[CONF_NAME]
    proximity = Proximity(hass, friendly_name, coordinator)
    await proximity.async_added_to_hass()
    proximity.async_write_ha_state()

    if used_in := entity_used_in(hass, f"{DOMAIN}.{friendly_name}"):
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Get the zones and offsets from configuration.yaml."""
    if DOMAIN in config:
        for friendly_name, proximity_config in config[DOMAIN].items():
            _LOGGER.debug("import %s with config:%s", friendly_name, proximity_config)
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_NAME: friendly_name,
                        CONF_ZONE: f"zone.{proximity_config[CONF_ZONE]}",
                        CONF_TRACKED_ENTITIES: proximity_config[CONF_DEVICES],
                        CONF_IGNORED_ZONES: [
                            f"zone.{zone}"
                            for zone in proximity_config[CONF_IGNORED_ZONES]
                        ],
                        CONF_TOLERANCE: proximity_config[CONF_TOLERANCE],
                        CONF_UNIT_OF_MEASUREMENT: proximity_config.get(
                            CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit
                        ),
                    },
                )
            )

        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Proximity",
            },
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Proximity from a config entry."""
    _LOGGER.debug("setup %s with config:%s", entry.title, entry.data)

    hass.data.setdefault(DOMAIN, {})

    coordinator = ProximityDataUpdateCoordinator(hass, entry.title, dict(entry.data))

    entry.async_on_unload(
        async_track_state_change(
            hass,
            entry.data[CONF_TRACKED_ENTITIES],
            coordinator.async_check_proximity_state_change,
        )
    )

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass,
            entry.data[CONF_TRACKED_ENTITIES],
            coordinator.async_check_tracked_entity_change,
        )
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if entry.source == SOURCE_IMPORT:
        await _async_setup_legacy(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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
    def data(self) -> dict[str, str | int | None]:
        """Get data from coordinator."""
        return self.coordinator.data.proximity

    @property
    def state(self) -> str | float:
        """Return the state."""
        if isinstance(distance := self.data[ATTR_DIST_TO], str):
            return distance
        return self.coordinator.convert_legacy(cast(int, distance))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            ATTR_DIR_OF_TRAVEL: str(self.data[ATTR_DIR_OF_TRAVEL] or STATE_UNKNOWN),
            ATTR_NEAREST: str(self.data[ATTR_NEAREST]),
        }
