"""Support for KEBA charging station binary sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, KebaHandler


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba: KebaHandler = hass.data[DOMAIN]

    sensors = [
        KebaBinarySensor(
            keba,
            "Online",
            "Status",
            "device_state",
            BinarySensorDeviceClass.CONNECTIVITY,
        ),
        KebaBinarySensor(
            keba,
            "Plug",
            "Plug",
            "plug_state",
            BinarySensorDeviceClass.PLUG,
        ),
        KebaBinarySensor(
            keba,
            "State",
            "Charging State",
            "charging_state",
            BinarySensorDeviceClass.POWER,
        ),
        KebaBinarySensor(
            keba,
            "Tmo FS",
            "Failsafe Mode",
            "failsafe_mode_state",
            BinarySensorDeviceClass.SAFETY,
        ),
    ]
    async_add_entities(sensors)


class KebaBinarySensor(BinarySensorEntity):
    """Representation of a binary sensor of a KEBA charging station."""

    _attr_should_poll = False

    def __init__(
        self,
        keba: KebaHandler,
        key: str,
        name: str,
        entity_type: str,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the KEBA Sensor."""
        self._key = key
        self._keba = keba
        self._attributes: dict[str, Any] = {}

        self._attr_device_class = device_class
        self._attr_name = f"{keba.device_name} {name}"
        self._attr_unique_id = f"{keba.device_id}_{entity_type}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the binary sensor."""
        return self._attributes

    async def async_update(self) -> None:
        """Get latest cached states from the device."""
        if self._key == "Online":
            self._attr_is_on = self._keba.get_value(self._key)

        elif self._key == "Plug":
            self._attr_is_on = self._keba.get_value("Plug_plugged")
            self._attributes["plugged_on_wallbox"] = self._keba.get_value(
                "Plug_wallbox"
            )
            self._attributes["plug_locked"] = self._keba.get_value("Plug_locked")
            self._attributes["plugged_on_EV"] = self._keba.get_value("Plug_EV")

        elif self._key == "State":
            self._attr_is_on = self._keba.get_value("State_on")
            self._attributes["status"] = self._keba.get_value("State_details")
            self._attributes["max_charging_rate"] = str(
                self._keba.get_value("Max curr")
            )

        elif self._key == "Tmo FS":
            self._attr_is_on = not self._keba.get_value("FS_on")
            self._attributes["failsafe_timeout"] = str(self._keba.get_value("Tmo FS"))
            self._attributes["fallback_current"] = str(self._keba.get_value("Curr FS"))
        elif self._key == "Authreq":
            self._attr_is_on = self._keba.get_value(self._key) == 0

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
