"""Support for Launch Library sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import (
    ATTR_DESCRIPTION,
    ATTR_LAUNCH_FACILITY,
    ATTR_LAUNCH_PAD,
    ATTR_LAUNCH_PAD_COUNTRY_CODE,
    ATTR_LAUNCH_PROVIDER,
    ATTR_ORBIT,
    ATTR_REASON,
    ATTR_STREAM_LIVE,
    ATTR_TYPE,
    ATTR_WINDOW_END,
    ATTR_WINDOW_START,
    ATTRIBUTION,
    DOMAIN,
    ICON_CLOCK,
    ICON_LUCK,
    ICON_ROCKET,
    UPDATECOORDINATOR,
)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][UPDATECOORDINATOR]

    sensors = [
        NextLaunchSensor(coordinator, "Next launch"),
        LaunchTimeSensor(coordinator, "Launch time"),
        LaunchProbabilitySensor(coordinator, "Launch probability"),
        LaunchStatusSensor(coordinator, "Launch status"),
        LaunchMissionSensor(coordinator, "Launch mission"),
    ]

    async_add_entities(sensors, True)


class LLBaseEntity(CoordinatorEntity, SensorEntity):
    """Sensor base entity."""

    def __init__(self, coordinator, name):
        """Initialize a Launch Library entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}/{name}"

    def get_next_launch(self):
        """Return next launch."""
        return next((launch for launch in self.coordinator.data), None)


class NextLaunchSensor(LLBaseEntity):
    """Representation of the next launch sensor."""

    _attr_icon = ICON_ROCKET

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.name

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        next_launch = self.get_next_launch()
        return {
            ATTR_LAUNCH_PROVIDER: next_launch.launch_service_provider.name,
            ATTR_LAUNCH_PAD: next_launch.pad.name,
            ATTR_LAUNCH_FACILITY: next_launch.pad.location.name,
            ATTR_LAUNCH_PAD_COUNTRY_CODE: next_launch.pad.location.country_code,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class LaunchTimeSensor(LLBaseEntity):
    """Representation of the launch time sensor."""

    _attr_icon = ICON_CLOCK
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return parse_datetime(next_launch.net)

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        next_launch = self.get_next_launch()
        return {
            ATTR_WINDOW_START: next_launch.window_start,
            ATTR_WINDOW_END: next_launch.window_end,
            ATTR_STREAM_LIVE: next_launch.webcast_live,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class LaunchProbabilitySensor(LLBaseEntity):
    """Representation of the launch probability sensor."""

    _attr_icon = ICON_LUCK
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.probability

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class LaunchStatusSensor(LLBaseEntity):
    """Representation of launch status sensor."""

    _attr_icon = ICON_ROCKET

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.status.name

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        next_launch = self.get_next_launch()
        if next_launch.inhold:
            return {
                ATTR_REASON: next_launch.holdreason,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }


class LaunchMissionSensor(LLBaseEntity):
    """Representation of the launch mission sensor."""

    _attr_icon = ICON_ROCKET

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.mission.name

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        next_launch = self.get_next_launch()
        return {
            ATTR_DESCRIPTION: next_launch.mission.description,
            ATTR_TYPE: next_launch.mission.type,
            ATTR_ORBIT: next_launch.mission.orbit.name,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
