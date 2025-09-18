"""Support for Olarm binary sensors.

An Olarm device connected to an alarm system can have up to 192 zones, these are usually
door/window contacts and motion sensors. They can be either active or closed depending
if motion is detected or door/window is open.

The zones can also be bypassed so they are ignored if the alarm system is armed so
additional binary sensors are added for this. Alarm systems also monitor AC power
as they have battery backup so this is added as a binary sensor as well.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OlarmDataUpdateCoordinator
from .entity import OlarmEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class OlarmBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Olarm binary sensor entity."""

    value_fn: Callable[[OlarmDataUpdateCoordinator, int | None], bool]
    name_fn: Callable[[int, str], str]
    unique_id_fn: Callable[[str, int], str]


# Descriptions for the different Olarm binary sensor types
SENSOR_DESCRIPTIONS: dict[str, OlarmBinarySensorEntityDescription] = {
    "zone": OlarmBinarySensorEntityDescription(
        key="zone",
        value_fn=lambda coord, index: (
            coord.data is not None
            and coord.data.device_state is not None
            and coord.data.device_state.get("zones", [])[index] == "a"
        ),
        name_fn=lambda index, label: f"Zone {index + 1:03} - {label}",
        unique_id_fn=lambda device_id, index: f"{device_id}.zone.{index}",
    ),
    "zone_bypass": OlarmBinarySensorEntityDescription(
        key="zone_bypass",
        value_fn=lambda coord, index: (
            coord.data is not None
            and coord.data.device_state is not None
            and coord.data.device_state.get("zones", [])[index] == "b"
        ),
        name_fn=lambda index, label: f"Zone {index + 1:03} Bypass - {label}",
        unique_id_fn=lambda device_id, index: f"{device_id}.zone.bypass.{index}",
    ),
    "ac_power": OlarmBinarySensorEntityDescription(
        key="ac_power",
        value_fn=lambda coord, _: (
            coord.data is not None
            and coord.data.device_state is not None
            and coord.data.device_state.get("powerAC") == "ok"
        ),
        name_fn=lambda index, label: f"{label}",
        unique_id_fn=lambda device_id, index: f"{device_id}.ac_power",
    ),
}

CLASS_MAP: dict[int, BinarySensorDeviceClass] = {
    10: BinarySensorDeviceClass.DOOR,
    11: BinarySensorDeviceClass.WINDOW,
    20: BinarySensorDeviceClass.MOTION,
    21: BinarySensorDeviceClass.MOTION,
}


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
    device_id = config_entry.data["device_id"]
    zones = coordinator.data.device_state.get("zones", [])
    labels = coordinator.data.device_profile.get("zonesLabels")
    types = coordinator.data.device_profile.get("zonesTypes")
    for zone_index, zone_state in enumerate(zones):
        zone_label = labels[zone_index]
        zone_class = types[zone_index]
        for sensor_type in ("zone", "zone_bypass"):
            sensors.append(
                OlarmBinarySensor(
                    coordinator,
                    SENSOR_DESCRIPTIONS[sensor_type],
                    device_id,
                    zone_index,
                    zone_state,
                    zone_label,
                    zone_class,
                )
            )


def load_ac_power_sensor(coordinator, config_entry, sensors):
    """Load AC power sensor."""
    ac_power_state = (
        "on"
        if coordinator.data.device_state.get("powerAC") == "ok"
        or coordinator.data.device_state.get("power", {}).get("AC") == "1"
        else "off"
    )
    sensors.append(
        OlarmBinarySensor(
            coordinator,
            SENSOR_DESCRIPTIONS["ac_power"],
            config_entry.data["device_id"],
            0,
            ac_power_state,
            "AC Power",
            None,
        )
    )


class OlarmBinarySensor(OlarmEntity, BinarySensorEntity):
    """Define an Olarm Binary Sensor."""

    entity_description: OlarmBinarySensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: OlarmBinarySensorEntityDescription,
        device_id: str,
        sensor_index: int,
        sensor_state: str,
        sensor_label: str,
        sensor_class: int | None = None,
        link_id: int | None = None,
        link_name: str | None = "",
    ) -> None:
        """Init the class."""

        # Initialize base entity
        super().__init__(coordinator, device_id)

        # store description
        self.entity_description = description

        # set attributes via description
        self._attr_name = self.entity_description.name_fn(sensor_index, sensor_label)
        self._attr_unique_id = self.entity_description.unique_id_fn(
            device_id, sensor_index
        )

        _LOGGER.debug(
            "BinarySensor: init %s -> %s -> %s",
            self.entity_description.key,
            self._attr_name,
            sensor_state,
        )

        # set the device class if provided
        if sensor_class in CLASS_MAP:
            self._attr_device_class = CLASS_MAP[sensor_class]

        # custom attributes
        self.sensor_index = sensor_index
        self.sensor_state = sensor_state
        self.sensor_label = sensor_label
        self.sensor_class = sensor_class
        self.link_id = (
            link_id  # only used for olarm LINKs to track which LINK as can have upto 8
        )

        # initialize state via description
        self._attr_is_on = self.entity_description.value_fn(
            self.coordinator, self.sensor_index
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return

        # Extract the data from coordinator
        device_state = self.coordinator.data.device_state

        # Store the previous state to check if it changed
        previous_state = self._attr_is_on

        # compute state using description
        if device_state is not None:
            self._attr_is_on = self.entity_description.value_fn(
                self.coordinator, self.sensor_index
            )

        # Only schedule state update if the state actually changed
        if self._attr_is_on != previous_state:
            self.async_write_ha_state()
