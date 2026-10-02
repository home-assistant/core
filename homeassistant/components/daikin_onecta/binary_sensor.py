"""Support for Daikin binary sensor sensors."""

import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device import DaikinOnectaDevice
from .entity_descriptions import BINARY_SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from .coordinator import OnectaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, async_add_entities) -> None:
    """Old way of setting up the Daikin sensors.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors = []
    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            for (
                value,
                characteristic,
            ) in management_point.simple_characteristics().items():
                if characteristic.values is None and isinstance(
                    characteristic.value, bool
                ):
                    sensors.append(
                        DaikinBinarySensor(
                            device,
                            coordinator,
                            management_point.embedded_id,
                            management_point.management_point_type,
                            value,
                        )
                    )

    async_add_entities(sensors)


class DaikinBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represent a boolean Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator,
        embedded_id,
        management_point_type,
        value,
    ) -> None:
        """Initialize the binary sensor from a device characteristic."""
        _LOGGER.info("DaikinBinarySensor '%s' '%s'", management_point_type, value)
        super().__init__(coordinator)
        self._device = device
        self._management_point_type = management_point_type
        mpt = management_point_type[0].upper() + management_point_type[1:]
        assert self._device.ha_device_id is not None
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + embedded_id)},
            "name": self._device.name + " " + mpt,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, embedded_id)
        self._embedded_id = embedded_id
        self._value = value
        self._attr_unique_id = (
            f"{self._device.id}_{self._embedded_id}_None_{self._value}"
        )
        self._attr_has_entity_name = True
        self.entity_description = BINARY_SENSOR_DESCRIPTIONS[value]
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports binary sensor '%s'",
            device.name,
            self._embedded_id,
            self._value,
        )

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._attr_is_on = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    def sensor_value(self):
        """Return the binary characteristic value."""
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            point.characteristic(self._value) if point is not None else None
        )
        result = characteristic.value if characteristic is not None else None
        _LOGGER.debug(
            "Device '%s' binary sensor '%s' value '%s'",
            self._device.name,
            self._value,
            result,
        )
        return result
