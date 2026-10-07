"""Support for WLED sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from wled import Device as WLEDDevice

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
from .entity import WLEDEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WLEDSensorEntityDescription(SensorEntityDescription):
    """Describes WLED sensor entity."""

    exists_fn: Callable[[WLEDDevice], bool] = lambda _: True
    value_fn: Callable[[WLEDDevice], datetime | StateType]


SENSORS: tuple[WLEDSensorEntityDescription, ...] = (
    WLEDSensorEntityDescription(
        key="estimated_current",
        translation_key="estimated_current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.power,
        # The power budget is only reported for a global current limit, while
        # the estimate itself is also reported when limiting per output.
        exists_fn=lambda device: bool(device.info.leds.power),
    ),
    WLEDSensorEntityDescription(
        key="info_leds_count",
        translation_key="info_leds_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.count,
    ),
    WLEDSensorEntityDescription(
        key="info_leds_max_power",
        translation_key="info_leds_max_power",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=lambda device: device.info.leds.max_power,
        exists_fn=lambda device: bool(device.info.leds.max_power),
    ),
    WLEDSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: utcnow() - device.info.uptime,
    ),
    WLEDSensorEntityDescription(
        key="free_heap",
        translation_key="free_heap",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.free_heap,
    ),
    WLEDSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.signal if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.rssi if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_channel",
        translation_key="wifi_channel",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.channel if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_bssid",
        translation_key="wifi_bssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.bssid if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="ip",
        translation_key="ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.ip,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED sensor based on a config entry."""
    coordinator = entry.runtime_data
    added: set[str] = set()

    # Sensors added before stay, even when the device doesn't report what they
    # need right now, like the current while the light is off.
    registered = {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registry_entry.domain == SENSOR_DOMAIN
    }
    mac_address = coordinator.data.info.mac_address

    @callback
    def _async_add_sensors() -> None:
        """Add the sensors the device reports, as soon as it does.

        Some only show up later: WLED reports no current while the light is
        off, so a device that's off when set up gets those sensors once it's on.
        """
        sensors = [
            WLEDSensorEntity(coordinator, description)
            for description in SENSORS
            if description.key not in added
            and (
                description.exists_fn(coordinator.data)
                or f"{mac_address}_{description.key}" in registered
            )
        ]
        added.update(sensor.entity_description.key for sensor in sensors)
        if sensors:
            async_add_entities(sensors)

    _async_add_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_sensors))


class WLEDSensorEntity(WLEDEntity, SensorEntity):
    """Defines a WLED sensor entity."""

    entity_description: WLEDSensorEntityDescription

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        description: WLEDSensorEntityDescription,
    ) -> None:
        """Initialize a WLED sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{description.key}"

    @property
    @override
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
