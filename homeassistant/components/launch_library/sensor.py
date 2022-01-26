"""Support for Launch Library sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from pylaunches.objects.launch import Launch
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import parse_datetime

from . import LaunchLibraryData
from .const import DOMAIN

DEFAULT_NEXT_LAUNCH_NAME = "Next launch"

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NEXT_LAUNCH_NAME): cv.string}
)


@dataclass
class LaunchLibrarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Launch], datetime | int | str | None]
    attributes_fn: Callable[[Launch], dict[str, Any] | None]


@dataclass
class LaunchLibrarySensorEntityDescription(
    SensorEntityDescription, LaunchLibrarySensorEntityDescriptionMixin
):
    """Describes a Next Launch sensor entity."""


SENSOR_DESCRIPTIONS: tuple[LaunchLibrarySensorEntityDescription, ...] = (
    LaunchLibrarySensorEntityDescription(
        key="next_launch",
        icon="mdi:rocket-launch",
        name="Next launch",
        value_fn=lambda nl: nl.name,
        attributes_fn=lambda nl: {
            "provider": nl.launch_service_provider.name,
            "pad": nl.pad.name,
            "facility": nl.pad.location.name,
            "provider_country_code": nl.pad.location.country_code,
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_time",
        icon="mdi:clock-outline",
        name="Launch time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda nl: parse_datetime(nl.net),
        attributes_fn=lambda nl: {
            "window_start": nl.window_start,
            "window_end": nl.window_end,
            "stream_live": nl.webcast_live,
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_probability",
        icon="mdi:dice-multiple",
        name="Launch Probability",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda nl: None if nl.probability == -1 else nl.probability,
        attributes_fn=lambda nl: None,
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_status",
        icon="mdi:rocket-launch",
        name="Launch status",
        value_fn=lambda nl: nl.status.name,
        attributes_fn=lambda nl: {"reason": nl.holdreason} if nl.inhold else None,
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_mission",
        icon="mdi:orbit",
        name="Launch mission",
        value_fn=lambda nl: nl.mission.name,
        attributes_fn=lambda nl: {
            "mission_type": nl.mission.type,
            "target_orbit": nl.mission.orbit.name,
            "description": nl.mission.description,
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="starship_launch",
        icon="mdi:rocket",
        name="Next Starship launch",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sl: parse_datetime(sl.net),
        attributes_fn=lambda sl: {
            "title": sl.mission.name,
            "status": sl.status.name,
            "target_orbit": sl.mission.orbit.name,
            "description": sl.mission.description,
        },
    ),
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
    name = entry.data.get(CONF_NAME, DEFAULT_NEXT_LAUNCH_NAME)
    coordinator: DataUpdateCoordinator[LaunchLibraryData] = hass.data[DOMAIN]

    async_add_entities(
        LaunchLibrarySensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            description=description,
            name=name if description.key == "next_launch" else None,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class LaunchLibrarySensor(CoordinatorEntity, SensorEntity):
    """Representation of the next launch sensors."""

    _attr_attribution = "Data provided by Launch Library."
    _next_launch: Launch | None = None
    entity_description: LaunchLibrarySensorEntityDescription
    coordinator: DataUpdateCoordinator[LaunchLibraryData]

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[LaunchLibraryData],
        entry_id: str,
        description: LaunchLibrarySensorEntityDescription,
        name: str | None = None,
    ) -> None:
        """Initialize a Launch Library sensor."""
        super().__init__(coordinator)
        if name:
            self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> datetime | str | int | None:
        """Return the state of the sensor."""
        if self._next_launch is None:
            return None
        return self.entity_description.value_fn(self._next_launch)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if self._next_launch is None:
            return None
        return self.entity_description.attributes_fn(self._next_launch)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and self._next_launch is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key == "starship_launch":
            launches = self.coordinator.data["starship_events"].upcoming.launches
        else:
            launches = self.coordinator.data["upcoming_launches"]

        self._next_launch = next((launch for launch in (launches)), None)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
