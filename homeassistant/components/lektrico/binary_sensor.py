"""Support for Lektrico charging station binary sensors."""


from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class LektricoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes the Lektrico binary sensor entities."""

    get_is_on: Callable[[Any], bool] | None = None


@dataclass
class HasActiveErrorsBinarySensorEntityDescription(
    LektricoBinarySensorEntityDescription
):
    """A class that describes the Lektrico Has Active Errors binary sensor entity."""

    @classmethod
    def set_extra_state_att(cls, lektrico_binary_sensor: LektricoBinarySensor) -> None:
        """Get the has_active_errors."""
        if hasattr(lektrico_binary_sensor.coordinator.data, "state_e_activated"):
            # error types exist => set their values in _attr_extra_state_attributes
            lektrico_binary_sensor.set_attr_extra_state_attributes_for_errors(
                lektrico_binary_sensor.coordinator.data.state_e_activated,
                lektrico_binary_sensor.coordinator.data.overtemp,
                lektrico_binary_sensor.coordinator.data.critical_temp,
                lektrico_binary_sensor.coordinator.data.overcurrent,
                lektrico_binary_sensor.coordinator.data.meter_fault,
                lektrico_binary_sensor.coordinator.data.voltage_error,
                lektrico_binary_sensor.coordinator.data.rcd_error,
            )


SENSORS: tuple[LektricoBinarySensorEntityDescription, ...] = (
    HasActiveErrorsBinarySensorEntityDescription(
        key="errors",
        name="Errors",
        device_class=BinarySensorDeviceClass.PROBLEM,
        get_is_on=lambda data: bool(data.has_active_errors),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    coordinator: LektricoDeviceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LektricoBinarySensor(
            description,
            coordinator,
            entry.data[CONF_FRIENDLY_NAME],
        )
        for description in SENSORS
    )


class LektricoBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """The entity class for Lektrico charging stations binary sensors."""

    entity_description: LektricoBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        description: LektricoBinarySensorEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.serial_number))},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=coordinator.data.fw_version,
        )

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
        if self.entity_description.get_is_on is None:
            return None
        return self.entity_description.get_is_on(self.coordinator.data)

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
