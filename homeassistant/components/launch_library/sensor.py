"""Support for Launch Library sensors."""
from __future__ import annotations

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
    ATTR_STREAM_LIVE,
    ATTR_WINDOW_END,
    ATTR_WINDOW_START,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_launch",
        icon="mdi:rocket-launch",
        name=DEFAULT_NAME,
    ),
    SensorEntityDescription(
        key="launch_time",
        icon="mdi:clock-outline",
        name="Launch time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="launch_probability",
        icon="mdi:horseshoe",
        name="Launch Probability",
        native_unit_of_measurement=PERCENTAGE,
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
        [
            NextLaunchSensor(
                coordinator,
                entry.entry_id,
                SENSOR_DESCRIPTIONS[0],
                name,
            ),
            LaunchTimeSensor(
                coordinator,
                entry.entry_id,
                SENSOR_DESCRIPTIONS[1],
            ),
            LaunchProbabilitySensor(
                coordinator,
                entry.entry_id,
                SENSOR_DESCRIPTIONS[2],
            ),
        ]
    )


class NextLaunchBaseSensor(CoordinatorEntity, SensorEntity):
    """Representation of the base next launch sensor."""

    _attr_attribution = ATTRIBUTION
    _next_launch: Launch | None = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry_id: str,
        description: SensorEntityDescription,
        name: str | None = None,
    ) -> None:
        """Initialize a Launch Library entity."""
        super().__init__(coordinator)
        if name:
            self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description

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


class NextLaunchSensor(NextLaunchBaseSensor):
    """Representation of the next launch information sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self._next_launch is None:
            return None
        return self._next_launch.name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if self._next_launch is None:
            return None
        return {
            ATTR_LAUNCH_PROVIDER: self._next_launch.launch_service_provider.name,
            ATTR_LAUNCH_PAD: self._next_launch.pad.name,
            ATTR_LAUNCH_FACILITY: self._next_launch.pad.location.name,
            ATTR_LAUNCH_PAD_COUNTRY_CODE: self._next_launch.pad.location.country_code,
        }


class LaunchTimeSensor(NextLaunchBaseSensor):
    """Representation of the next launch time sensor."""

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        if self._next_launch is None:
            return None
        return parse_datetime(self._next_launch.net)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if self._next_launch is None:
            return None
        return {
            ATTR_WINDOW_START: self._next_launch.window_start,
            ATTR_WINDOW_END: self._next_launch.window_end,
            ATTR_STREAM_LIVE: self._next_launch.webcast_live,
        }


class LaunchProbabilitySensor(NextLaunchBaseSensor):
    """Representation of the launch probability sensor."""

    @property
    def native_value(self) -> int | str | None:
        """Return the state of the sensor."""
        if self._next_launch is None:
            return None

        # Library will return -1 if the probability is unknown, therefore
        #  we check for it and return STATE_UNKNOWN instead so
        # it is represent correctly that the probability is unknown.
        if self._next_launch.probability == -1:
            return STATE_UNKNOWN
        return self._next_launch.probability
