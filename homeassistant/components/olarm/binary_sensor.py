"""Support for zones through the Olarm cloud API."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""

    _LOGGER.debug("config_entry -> %s", config_entry.data)

    # get coordinator
    coordinator = config_entry.runtime_data["coordinator"]

    # cycle through zones and create binary sensors
    sensors = []
    if coordinator.device_profile is not None and coordinator.device_state is not None:
        for zone_index, zone_state in enumerate(coordinator.device_state.get("zones")):
            sensors.append(
                OlarmBinarySensor(
                    "zone",
                    config_entry.data["device_id"],
                    coordinator.device_name,
                    zone_index,
                    zone_state,
                    coordinator.device_profile.get("zonesLabels")[zone_index],
                    coordinator.device_profile.get("zonesTypes")[zone_index],
                )
            )
            # load bypass entities if enabled
            if config_entry.data.get("load_zones_bypass_entities"):
                sensors.append(
                    OlarmBinarySensor(
                        "zone_bypass",
                        config_entry.data["device_id"],
                        coordinator.device_name,
                        zone_index,
                        zone_state,
                        coordinator.device_profile.get("zonesLabels")[zone_index],
                        coordinator.device_profile.get("zonesTypes")[zone_index],
                    )
                )

    # setup binary sensor for AC power
    if coordinator.device_state is not None:
        ac_power_state = "off"
        if coordinator.device_state.get("powerAC") == "ok":
            ac_power_state = "on"
        if coordinator.device_state.get("power", {}).get("AC") == "1":
            ac_power_state = "on"
        sensors.append(
            OlarmBinarySensor(
                "ac_power",
                config_entry.data["device_id"],
                coordinator.device_name,
                0,
                ac_power_state,
                "AC Power",
            )
        )

    # load LINK inputs and outputs / relays in latch mode
    if (
        coordinator.device_profile_links is not None
        and len(coordinator.device_profile_links) > 0
        and coordinator.device_links is not None
    ):
        for link_id, link_data in coordinator.device_profile_links.items():
            link_name = link_data.get("name", "Unnamed Link")

            io_items = link_data.get("io", [])
            for io_index, io in enumerate(io_items):
                # Only create sensors for enabled inputs
                if io.get("enabled"):
                    if io.get("type") == "input":
                        sensors.append(
                            OlarmBinarySensor(
                                "link_input",
                                config_entry.data["device_id"] + "_" + link_id,
                                coordinator.device_name + " - " + link_name,
                                io_index,
                                coordinator.device_links[link_id]["inputs"][io_index],
                                io.get("label"),
                                None,
                                link_id,
                            )
                        )
                    elif io.get("type") == "output" and io.get("outputMode") == "latch":
                        sensors.append(
                            OlarmBinarySensor(
                                "link_output",
                                config_entry.data["device_id"] + "_" + link_id,
                                coordinator.device_name + " - " + link_name,
                                io_index,
                                coordinator.device_links[link_id]["outputs"][io_index],
                                io.get("label"),
                                None,
                                link_id,
                            )
                        )

            relay_items = link_data.get("relays", [])
            for relay_index, relay in enumerate(relay_items):
                # only create sensors for enabled relays in latch mode
                if relay.get("enabled") and relay.get("relayMode") == "latch":
                    sensors.append(
                        OlarmBinarySensor(
                            "link_relay",
                            config_entry.data["device_id"] + "_" + link_id,
                            coordinator.device_name + " - " + link_name,
                            relay_index,
                            coordinator.device_links[link_id]["relays"][relay_index],
                            relay.get("label"),
                            None,
                            link_id,
                        )
                    )

    # load Max IO inputs and outputs in latch mode
    if (
        coordinator.device_profile_io is not None
        and coordinator.device_profile_io.get("io") is not None
        and coordinator.device_io is not None
    ):
        for io_index, io in enumerate(coordinator.device_profile_io.get("io")):
            if io.get("enabled"):
                if io.get("type") == "input":
                    sensors.append(
                        OlarmBinarySensor(
                            "max_input",
                            config_entry.data["device_id"],
                            coordinator.device_name,
                            io_index,
                            coordinator.device_io["inputs"][io_index],
                            io.get("label"),
                        )
                    )
                elif io.get("type") == "output" and io.get("outputMode") == "latch":
                    sensors.append(
                        OlarmBinarySensor(
                            "max_output",
                            config_entry.data["device_id"],
                            coordinator.device_name,
                            io_index,
                            coordinator.device_io["outputs"][io_index],
                            io.get("label"),
                        )
                    )

    async_add_entities(sensors)


class OlarmBinarySensor(BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    def __init__(
        self,
        sensor_type,
        device_id,
        base_name,
        sensor_index,
        sensor_state,
        sensor_label,
        sensor_class=None,
        link_id=None,
    ) -> None:
        """Init the class."""

        # set attributes
        self._attr_name = f"{base_name} - Zone {sensor_index + 1:03} - {sensor_label}"
        self._attr_unique_id = f"{device_id}.zone.{sensor_index}"
        if sensor_type == "zone_bypass":
            self._attr_name = (
                f"{base_name} - Zone {sensor_index + 1:03} Bypass - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.zone.bypass.{sensor_index}"
        if sensor_type == "ac_power":
            self._attr_name = f"{base_name} - {sensor_label}"
            self._attr_unique_id = f"{device_id}.ac_power"
        if sensor_type == "link_input":
            self._attr_name = (
                f"{base_name} - LINK Input {sensor_index + 1:02} - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.link.input.{sensor_index}"
        if sensor_type == "link_output":
            self._attr_name = (
                f"{base_name} - LINK Output {sensor_index + 1:02} - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.link.output.{sensor_index}"
        if sensor_type == "link_relay":
            self._attr_name = (
                f"{base_name} - LINK Relay {sensor_index + 1:02} - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.link.relay.{sensor_index}"
        if sensor_type == "max_input":
            self._attr_name = (
                f"{base_name} - MAX Input {sensor_index + 1:02} - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.max.input.{sensor_index}"
        if sensor_type == "max_output":
            self._attr_name = (
                f"{base_name} - MAX Output {sensor_index + 1:02} - {sensor_label}"
            )
            self._attr_unique_id = f"{device_id}.max.output.{sensor_index}"

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
        self.device_id = device_id
        self.base_name = base_name
        self.sensor_index = sensor_index
        self.sensor_state = sensor_state
        self.sensor_label = sensor_label
        self.sensor_class = sensor_class
        self.link_id = (
            link_id  # only used for olarm LINKs to track which LINK as can have upto 8
        )
        self._unsubscribe_dispatcher = None

        # set state if zone is active[a] or closed[c] or bypassed[b]
        if (
            (self.sensor_type == "zone" and self.sensor_state == "a")
            or (self.sensor_type == "zone_bypass" and self.sensor_state == "b")
            or (self.sensor_type == "ac_power" and self.sensor_state == "on")
            or (
                (self.sensor_type in {"link_input", "max_input"})
                and self.sensor_state == "high"
            )
            or (
                (self.sensor_type in {"link_output", "max_output"})
                and self.sensor_state == "closed"
            )
            or ((self.sensor_type in {"link_relay"}) and self.sensor_state == "latched")
        ):
            self._attr_is_on = True
        else:
            self._attr_is_on = False

        # Set extra state attributes for zone type
        if self.sensor_type == "zone":
            self._attr_extra_state_attributes = {"bypassed": self.sensor_state == "b"}

    async def async_added_to_hass(self) -> None:
        """Register the signal listener when the entity is added."""
        await super().async_added_to_hass()
        self._unsubscribe_dispatcher = async_dispatcher_connect(
            self.hass, "olarm_mqtt_update", self._handle_mqtt_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from dispatcher when entity is removed."""
        if self._unsubscribe_dispatcher:
            self._unsubscribe_dispatcher()
        await super().async_will_remove_from_hass()

    def _handle_mqtt_update(self, device_id, device_state, device_links, device_io):
        """Handle state updates from MQTT messages."""

        # check if the device_id is the same as the device_id
        if device_id != self.device_id:
            return

        # update state
        if (self.sensor_type in {"zone", "zone_bypass"}) and device_state is not None:
            self.sensor_state = device_state.get("zones")[self.sensor_index]
        elif self.sensor_type == "ac_power" and device_state is not None:
            ac_power_state = "off"
            if device_state.get("powerAC") == "ok":
                ac_power_state = "on"
            if device_state.get("power", {}).get("AC") == "1":
                ac_power_state = "on"
            self.sensor_state = ac_power_state
        elif self.sensor_type == "link_input" and device_links is not None:
            self.sensor_state = device_links.get(self.link_id).get("inputs")[
                self.sensor_index
            ]
        elif self.sensor_type == "link_output" and device_links is not None:
            self.sensor_state = device_links.get(self.link_id).get("outputs")[
                self.sensor_index
            ]
        elif self.sensor_type == "max_input" and device_io is not None:
            self.sensor_state = device_io.get("inputs")[self.sensor_index]
        elif self.sensor_type == "max_output" and device_io is not None:
            self.sensor_state = device_io.get("outputs")[self.sensor_index]

        # set state if zone is active[a] or closed[c] or bypassed[b]
        if (
            (self.sensor_type == "zone" and self.sensor_state == "a")
            or (self.sensor_type == "zone_bypass" and self.sensor_state == "b")
            or (self.sensor_type == "ac_power" and self.sensor_state == "on")
            or (
                (self.sensor_type in {"link_input", "max_input"})
                and self.sensor_state == "high"
            )
            or (
                (self.sensor_type in {"link_output", "max_output"})
                and self.sensor_state == "closed"
            )
            or ((self.sensor_type in {"link_relay"}) and self.sensor_state == "latched")
        ):
            self._attr_is_on = True
        else:
            self._attr_is_on = False

        # set extra state attributes if applicable
        if self.sensor_type == "zone":
            self._attr_extra_state_attributes = {"bypassed": self.sensor_state == "b"}

        self.schedule_update_ha_state()

    @property
    def name(self) -> str | None:
        """The name of the zone from the Alarm Panel."""
        return self._attr_name

    @property
    def is_on(self) -> bool | None:
        """Whether the sensor/zone is active or not."""
        return self._attr_is_on
