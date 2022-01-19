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
from homeassistant.const import CONF_NAME, PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import parse_datetime

from .const import (
    ATTR_LAUNCH_FACILITY,
    ATTR_LAUNCH_PAD,
    ATTR_LAUNCH_PAD_COUNTRY_CODE,
    ATTR_LAUNCH_PROVIDER,
    ATTR_REASON,
    ATTR_STREAM_LIVE,
    ATTR_WINDOW_END,
    ATTR_WINDOW_START,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    LAUNCH_PROBABILITY,
    LAUNCH_STATUS,
    LAUNCH_TIME,
    NEXT_LAUNCH,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


@dataclass
class NextLaunchSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Launch], datetime | int | str | None]
    attributes_fn: Callable[[Launch], dict[str, Any] | None]


@dataclass
class NextLaunchSensorEntityDescription(
    SensorEntityDescription, NextLaunchSensorEntityDescriptionMixin
):
    """Describes a Next Launch sensor entity."""


SENSOR_DESCRIPTIONS: tuple[NextLaunchSensorEntityDescription, ...] = (
    NextLaunchSensorEntityDescription(
        key=NEXT_LAUNCH,
        icon="mdi:rocket-launch",
        name=DEFAULT_NAME,
        value_fn=lambda next_launch: next_launch.name,
        attributes_fn=lambda next_launch: {
            ATTR_LAUNCH_PROVIDER: next_launch.launch_service_provider.name,
            ATTR_LAUNCH_PAD: next_launch.pad.name,
            ATTR_LAUNCH_FACILITY: next_launch.pad.location.name,
            ATTR_LAUNCH_PAD_COUNTRY_CODE: next_launch.pad.location.country_code,
        },
    ),
    NextLaunchSensorEntityDescription(
        key=LAUNCH_TIME,
        icon="mdi:clock-outline",
        name="Launch time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda next_launch: parse_datetime(next_launch.net),
        attributes_fn=lambda next_launch: {
            ATTR_WINDOW_START: next_launch.window_start,
            ATTR_WINDOW_END: next_launch.window_end,
            ATTR_STREAM_LIVE: next_launch.webcast_live,
        },
    ),
    NextLaunchSensorEntityDescription(
        key=LAUNCH_PROBABILITY,
        icon="mdi:dice-multiple",
        name="Launch Probability",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda next_launch: next_launch.probability
        if next_launch.probability != -1
        else STATE_UNKNOWN,
        attributes_fn=lambda next_launch: None,
    ),
    NextLaunchSensorEntityDescription(
        key=LAUNCH_STATUS,
        icon="mdi:rocket-launch",
        name="Launch status",
        value_fn=lambda next_launch: next_launch.status.name,
        attributes_fn=lambda next_launch: {
            ATTR_REASON: next_launch.holdreason,
        }
        if next_launch.inhold
        else None,
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
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    coordinator = hass.data[DOMAIN]

    async_add_entities(
        NextLaunchSensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            description=description,
            name=name if description.key == NEXT_LAUNCH else None,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class NextLaunchSensor(CoordinatorEntity, SensorEntity):
    """Representation of the next launch sensors."""

    _attr_attribution = ATTRIBUTION
    _next_launch: Launch | None = None
    entity_description: NextLaunchSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        description: NextLaunchSensorEntityDescription,
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
        self._next_launch = next((launch for launch in self.coordinator.data), None)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
