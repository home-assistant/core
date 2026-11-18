"""Support for Genius Hub sensor devices."""

from datetime import timedelta
from typing import Any, override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import GeniusHubConfigEntry
from .const import (
    DOMAIN,
    GH_ATTR_NAME,
    GH_ATTR_SETPOINT,
    GH_ATTR_TEMPERATURE,
    GH_BATTERY_LEVEL_ATTR,
    GH_LEVEL_MAPPING,
    GH_TYPE,
    IDENTIFIER_ZONE,
)
from .entity import GeniusDevice, GeniusEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Genius Hub sensor entities."""

    coordinator = entry.runtime_data

    entities: list[GeniusBattery | GeniusIssue] = [
        GeniusBattery(coordinator, d, GH_BATTERY_LEVEL_ATTR)
        for d in coordinator.client.device_objs
        if GH_BATTERY_LEVEL_ATTR in d.data["state"]
    ]
    entities.extend([GeniusIssue(coordinator, i) for i in list(GH_LEVEL_MAPPING)])
    entities.extend(
        [
            GeniusTemp(coordinator, z)
            for z in coordinator.client.zone_objs
            if z.data.get(GH_ATTR_TEMPERATURE) and not z.data.get(GH_ATTR_SETPOINT)
        ]
    )

    async_add_entities(entities)


class GeniusBattery(GeniusDevice, SensorEntity):
    """Representation of a Genius Hub sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE

    def __init__(self, coordinator, device, state_attr) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)

        self._state_attr = state_attr

        self._attr_name = f"{device.type} {device.id}"

    @property
    @override
    def icon(self) -> str:
        """Return the icon of the sensor."""
        if "_state" in self._device.data:  # only for v3 API
            interval = timedelta(
                seconds=self._device.data["_state"].get("wakeupInterval", 30 * 60)
            )
            if (
                not self._last_comms
                or self._last_comms < dt_util.utcnow() - interval * 3
            ):
                return "mdi:battery-unknown"

        battery_level = self._device.data["state"][self._state_attr]
        if battery_level == 255:
            return "mdi:battery-unknown"
        if battery_level < 40:
            return "mdi:battery-alert"

        icon = "mdi:battery"
        if battery_level <= 95:
            icon += f"-{round(battery_level / 10 - 0.01) * 10}"

        return icon

    @property
    @override
    def native_value(self) -> int:
        """Return the state of the sensor."""
        level = self._device.data["state"][self._state_attr]
        return level if level != 255 else 0


class GeniusIssue(GeniusEntity, SensorEntity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, coordinator, level) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._hub = coordinator.client
        self._unique_id = f"{coordinator.hub_uid}_{GH_LEVEL_MAPPING[level]}"

        self._attr_name = f"GeniusHub {GH_LEVEL_MAPPING[level]}"
        self._level = level
        self._update_issues()

    @property
    @override
    def native_value(self) -> int:
        """Return the number of issues."""
        return len(self._issues)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {f"{self._level}_list": self._issues}

    async def async_update(self) -> None:
        """Process the sensor's state data."""
        self._update_issues()

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Entity device info."""
        return DeviceInfo(identifiers={(DOMAIN, self._hub.uid)})

    def _update_issues(self):
        self._issues = [
            i["description"] for i in self._hub.issues if i["level"] == self._level
        ]


class GeniusTemp(GeniusEntity, SensorEntity):
    """Representation of a Genius Hub sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, zone) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._hub = coordinator.client
        self._unique_id = f"{coordinator.hub_uid}_{zone.data.get(GH_TYPE)}_temperature"
        self._id = zone.id
        self._temperature = zone.data.get(GH_ATTR_TEMPERATURE)

        self._attr_name = f"{zone.data.get(GH_ATTR_NAME)} Temperature"

    @property
    @override
    def native_value(self) -> int:
        """Return the temperature of the sensor."""
        return self._temperature

    async def async_update(self) -> None:
        """Process the sensor's state data."""
        for z in self.coordinator.client.zone_objs:
            if z.id == self._id:
                self._temperature = z.data.get(GH_ATTR_TEMPERATURE)
                break

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Entity device info."""
        return DeviceInfo(identifiers={(DOMAIN, IDENTIFIER_ZONE.format(self._id))})
