"""A platform that to monitor Uptime Robot monitors."""
from datetime import timedelta
import logging

import async_timeout
from pyuptimerobot import UptimeRobot
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

ATTR_TARGET = "target"

ATTRIBUTION = "Data provided by Uptime Robot"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Uptime Robot binary_sensors."""
    uptime_robot_api = UptimeRobot()
    api_key = config[CONF_API_KEY]

    def api_wrapper():
        return uptime_robot_api.getMonitors(api_key)

    async def async_update_data():
        """Fetch data from API UptimeRobot API."""
        async with async_timeout.timeout(10):
            monitors = await hass.async_add_executor_job(api_wrapper)
            if not monitors or monitors.get("stat") != "ok":
                raise UpdateFailed("Error communicating with Uptime Robot API")
            return monitors

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="uptimerobot",
        update_method=async_update_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_refresh()

    if not coordinator.data or coordinator.data.get("stat") != "ok":
        _LOGGER.error("Error connecting to Uptime Robot")
        raise PlatformNotReady()

    async_add_entities(
        [
            UptimeRobotBinarySensor(
                coordinator,
                BinarySensorEntityDescription(
                    key=monitor["id"],
                    name=monitor["friendly_name"],
                    device_class=DEVICE_CLASS_CONNECTIVITY,
                ),
                target=monitor["url"],
            )
            for monitor in coordinator.data["monitors"]
        ],
    )


class UptimeRobotBinarySensor(BinarySensorEntity, CoordinatorEntity):
    """Representation of a Uptime Robot binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: BinarySensorEntityDescription,
        target: str,
    ) -> None:
        """Initialize Uptime Robot the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._target = target
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_TARGET: self._target,
        }

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        if monitor := next(
            (
                monitor
                for monitor in self.coordinator.data.get("monitors", [])
                if monitor["id"] == self.entity_description.key
            ),
            None,
        ):
            return monitor["status"] == 2
        return False
