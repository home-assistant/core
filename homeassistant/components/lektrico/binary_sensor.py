"""Support for Lektrico charging station binary sensors."""


from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_FRIENDLY_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes the Lektrico binary sensor entities."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool | None:
        """Return None."""
        return None


@dataclass
class HasActiveErrorsBinarySensorEntityDescription(
    LektricoBinarySensorEntityDescription
):
    """A class that describes the Lektrico Has Active Errors binary sensor entity."""

    @classmethod
    def get_is_on(cls, data: Any) -> bool:
        """Get the has_active_errors."""
        return bool(data.has_active_errors)

    @classmethod
    def set_extra_state_att(cls, lektrico_binary_sensor: LektricoBinarySensor) -> None:
        """Get the has_active_errors."""
        if hasattr(
            lektrico_binary_sensor.lektrico_device.data, "state_machine_e_activated"
        ):
            # error types exist => set their values in _attr_extra_state_attributes
            lektrico_binary_sensor.set_attr_extra_state_attributes_for_errors(
                lektrico_binary_sensor.lektrico_device.data.state_machine_e_activated,
                lektrico_binary_sensor.lektrico_device.data.overtemp,
                lektrico_binary_sensor.lektrico_device.data.critical_temp,
                lektrico_binary_sensor.lektrico_device.data.overcurrent,
                lektrico_binary_sensor.lektrico_device.data.meter_fault,
                lektrico_binary_sensor.lektrico_device.data.voltage_error,
                lektrico_binary_sensor.lektrico_device.data.rcd_error,
            )


SENSORS: tuple[LektricoBinarySensorEntityDescription, ...] = (
    HasActiveErrorsBinarySensorEntityDescription(
        key="has_active_errors",
        name="Errors",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    _lektrico_device: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    sensors = [
        LektricoBinarySensor(
            sensor_desc,
            _lektrico_device,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for sensor_desc in SENSORS
    ]

    async_add_entities(sensors, False)


class LektricoBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """The entity class for Lektrico charging stations binary sensors."""

    entity_description: LektricoBinarySensorEntityDescription

    def __init__(
        self,
        description: LektricoBinarySensorEntityDescription,
        _lektrico_device: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(_lektrico_device)
        self.friendly_name = friendly_name
        self.serial_number = _lektrico_device.serial_number
        self.board_revision = _lektrico_device.board_revision
        self.entity_description = description

        self._attr_name = f"{self.friendly_name} {description.name}"
        self._attr_unique_id = f"{self.serial_number}_{description.name}"
        # ex: 500006_No Authorisation

        self.lektrico_device = _lektrico_device

        # add extra_state_attributes for HasActiveErrorsBinarySensorEntityDescription
        if isinstance(description, HasActiveErrorsBinarySensorEntityDescription):
            self._attr_extra_state_attributes = {
                "state_e_activated": "",
                "overtemp": "",
                "critical_temp": "",
                "overcurrent": "",
                "meter_fault": "",
                "voltage_error": "",
                "rcd_error": "",
            }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        # set extra_state_attributes
        if isinstance(
            self.entity_description, HasActiveErrorsBinarySensorEntityDescription
        ):
            self.entity_description.set_extra_state_att(self)
        return self.entity_description.get_is_on(self.lektrico_device.data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Lektrico charger."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.serial_number)},
            ATTR_NAME: self.friendly_name,
            ATTR_MANUFACTURER: "Lektrico",
            ATTR_MODEL: f"1P7K {self.serial_number} rev.{self.board_revision}",
            ATTR_SW_VERSION: self.lektrico_device.data.fw_version,
        }

    def set_attr_extra_state_attributes_for_errors(
        self,
        value1: bool,
        value2: bool,
        value3: bool,
        value4: bool,
        value5: bool,
        value6: bool,
        value7: bool,
    ) -> None:
        """Set _attr_extra_state_attributes for HasActiveErrors binary sensor."""
        self._attr_extra_state_attributes["state_e_activated"] = value1
        self._attr_extra_state_attributes["overtemp"] = value2
        self._attr_extra_state_attributes["critical_temp"] = value3
        self._attr_extra_state_attributes["overcurrent"] = value4
        self._attr_extra_state_attributes["meter_fault"] = value5
        self._attr_extra_state_attributes["voltage_error"] = value6
        self._attr_extra_state_attributes["rcd_error"] = value7
