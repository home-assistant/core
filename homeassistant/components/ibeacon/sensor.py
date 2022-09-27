"""Support for iBeacon device sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ibeacon_ble import iBeaconAdvertisement

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LENGTH_METERS, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_IBEACON_DEVICE_NEW
from .coordinator import IBeaconCoordinator
from .entity import IBeaconEntity


@dataclass
class IBeaconRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[iBeaconAdvertisement], int | None]


@dataclass
class IBeaconSensorEntityDescription(SensorEntityDescription, IBeaconRequiredKeysMixin):
    """Describes iBeacon sensor entity."""


SENSOR_DESCRIPTIONS = (
    IBeaconSensorEntityDescription(
        key="rssi",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value_fn=lambda ibeacon_advertisement: ibeacon_advertisement.rssi,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IBeaconSensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value_fn=lambda ibeacon_advertisement: ibeacon_advertisement.power,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IBeaconSensorEntityDescription(
        key="estimated_distance",
        name="Estimated Distance",
        icon="mdi:signal-distance-variant",
        native_unit_of_measurement=LENGTH_METERS,
        value_fn=lambda ibeacon_advertisement: ibeacon_advertisement.distance,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors for iBeacon Tracker component."""
    coordinator: IBeaconCoordinator = hass.data[DOMAIN]

    @callback
    def _async_device_new(
        unique_id: str,
        identifier: str,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Signal a new device."""
        async_add_entities(
            IBeaconSensorEntity(
                coordinator,
                description,
                identifier,
                unique_id,
                ibeacon_advertisement,
            )
            for description in SENSOR_DESCRIPTIONS
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_IBEACON_DEVICE_NEW, _async_device_new)
    )


class IBeaconSensorEntity(IBeaconEntity, SensorEntity):
    """An iBeacon sensor entity."""

    entity_description: IBeaconSensorEntityDescription

    def __init__(
        self,
        coordinator: IBeaconCoordinator,
        description: IBeaconSensorEntityDescription,
        identifier: str,
        device_unique_id: str,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Initialize an iBeacon sensor entity."""
        super().__init__(
            coordinator, identifier, device_unique_id, ibeacon_advertisement
        )
        self._attr_unique_id = f"{device_unique_id}_{description.key}"
        self.entity_description = description

    @callback
    def _async_seen(
        self,
        ibeacon_advertisement: iBeaconAdvertisement,
    ) -> None:
        """Update state."""
        self._attr_available = True
        self._ibeacon_advertisement = ibeacon_advertisement
        self.async_write_ha_state()

    @callback
    def _async_unavailable(self) -> None:
        """Update state."""
        self._attr_available = False
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._ibeacon_advertisement)
