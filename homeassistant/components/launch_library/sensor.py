"""Support for Launch Library sensors."""
from __future__ import annotations

import logging
from typing import Any

from pylaunches.objects.launch import Launch
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_AGENCY,
    ATTR_AGENCY_COUNTRY_CODE,
    ATTR_LAUNCH_TIME,
    ATTR_STREAM,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Launch Library configuration from yaml."""
    _LOGGER.warning(
        "Configuration of the launch_library platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    coordinator = hass.data[DOMAIN]

    async_add_entities(
        [
            NextLaunchSensor(coordinator, entry.entry_id, name),
        ]
    )


class NextLaunchSensor(CoordinatorEntity, SensorEntity):
    """Representation of the next launch sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:rocket-launch"

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry_id: str, name: str
    ) -> None:
        """Initialize a Launch Library entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_next_launch"

    def get_next_launch(self) -> Launch | None:
        """Return next launch."""
        return next((launch for launch in self.coordinator.data), None)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if next_launch := self.get_next_launch():
            self._attr_available = True
            return next_launch.name
        self._attr_available = False
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if not (next_launch := self.get_next_launch()):
            return None
        return {
            ATTR_LAUNCH_TIME: next_launch.net,
            ATTR_AGENCY: next_launch.launch_service_provider.name,
            ATTR_AGENCY_COUNTRY_CODE: next_launch.pad.location.country_code,
            ATTR_STREAM: next_launch.webcast_live,
        }
