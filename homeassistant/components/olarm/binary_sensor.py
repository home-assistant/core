"""Support for Olarm binary sensors."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import OlarmEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""

    # get coordinator
    coordinator = config_entry.runtime_data.coordinator

    # load binary sensors
    sensors: list[OlarmBinarySensor] = []
    load_zone_sensors(coordinator, config_entry, sensors)
    load_ac_power_sensor(coordinator, config_entry, sensors)

    async_add_entities(sensors)


def load_zone_sensors(coordinator, config_entry, sensors):
    """Load zone sensors and bypass sensors."""
    if (
        coordinator.data
        and coordinator.data.device_profile is not None
        and coordinator.data.device_state is not None
    ):
        for zone_index, zone_state in enumerate(
            coordinator.data.device_state.get("zones", [])
        ):
            # load zone entities
            sensors.append(
                OlarmBinarySensor(
                    coordinator,
                    "zone",
                    config_entry.data["device_id"],
                    zone_index,
                    zone_state,
                    coordinator.data.device_profile.get("zonesLabels")[zone_index],
                    coordinator.data.device_profile.get("zonesTypes")[zone_index],
                )
            )
            # load bypass entities
            sensors.append(
                OlarmBinarySensor(
                    coordinator,
                    "zone_bypass",
                    config_entry.data["device_id"],
                    zone_index,
                    zone_state,
                    coordinator.data.device_profile.get("zonesLabels")[zone_index],
                    coordinator.data.device_profile.get("zonesTypes")[zone_index],
                )
            )


def load_ac_power_sensor(coordinator, config_entry, sensors):
    """Load AC power sensor."""
    if coordinator.data and coordinator.data.device_state is not None:
        ac_power_state = "off"
        if coordinator.data.device_state.get("powerAC") == "ok":
            ac_power_state = "on"
        if coordinator.data.device_state.get("power", {}).get("AC") == "1":
            ac_power_state = "on"
        sensors.append(
            OlarmBinarySensor(
                coordinator,
                "ac_power",
                config_entry.data["device_id"],
                0,
                ac_power_state,
                "AC Power",
                None,
            )
        )


class OlarmBinarySensor(OlarmEntity, BinarySensorEntity):
    """Define an Olarm Binary Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type,
        device_id,
        sensor_index,
        sensor_state,
        sensor_label,
        sensor_class=None,
        link_id=None,
        link_name: str | None = "",
    ) -> None:
        """Init the class."""

        # Initialize base entity
        super().__init__(coordinator, device_id)

        # set attributes
        self._attr_name = f"Zone {sensor_index + 1:03} - {sensor_label}"
        self._attr_unique_id = f"{device_id}.zone.{sensor_index}"
        if sensor_type == "zone_bypass":
            self._attr_name = f"Zone {sensor_index + 1:03} Bypass - {sensor_label}"
            self._attr_unique_id = f"{device_id}.zone.bypass.{sensor_index}"
        if sensor_type == "ac_power":
            self._attr_name = f"{sensor_label}"
            self._attr_unique_id = f"{device_id}.ac_power"

        _LOGGER.debug(
            "BinarySensor: init %s -> %s -> %s",
            sensor_type,
            self._attr_name,
            sensor_state,
        )

        # set the class attribute if zone type is set
        if sensor_class == 10:
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif sensor_class == 11:
            self._attr_device_class = BinarySensorDeviceClass.WINDOW
        elif sensor_class in (20, 21):
            self._attr_device_class = BinarySensorDeviceClass.MOTION

        # custom attributes
        self.sensor_type = sensor_type
        self.sensor_index = sensor_index
        self.sensor_state = sensor_state
        self.sensor_label = sensor_label
        self.sensor_class = sensor_class
        self.link_id = (
            link_id  # only used for olarm LINKs to track which LINK as can have upto 8
        )

        # set state if zone is active[a] or closed[c] or bypassed[b]
        self._attr_is_on = self._determine_is_on()

    def _determine_is_on(self) -> bool:
        """Determine if the binary sensor should be on."""
        if self.sensor_type == "zone" and self.sensor_state == "a":
            return True
        if self.sensor_type == "zone_bypass" and self.sensor_state == "b":
            return True
        if self.sensor_type == "ac_power" and self.sensor_state == "on":
            return True
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return

        # Extract the data from coordinator
        device_state = self.coordinator.data.device_state

        # Store the previous state to check if it changed
        previous_state = self._attr_is_on

        # update state
        if (self.sensor_type in {"zone", "zone_bypass"}) and device_state is not None:
            self.sensor_state = device_state.get("zones", [])[self.sensor_index]
        elif self.sensor_type == "ac_power" and device_state is not None:
            ac_power_state = "off"
            if device_state.get("powerAC") == "ok":
                ac_power_state = "on"
            if device_state.get("power", {}).get("AC") == "1":
                ac_power_state = "on"
            self.sensor_state = ac_power_state

        # set state if zone is active[a] or closed[c] or bypassed[b]
        self._attr_is_on = self._determine_is_on()

        # Only schedule state update if the state actually changed
        if self._attr_is_on != previous_state:
            self.async_write_ha_state()
