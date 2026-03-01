"""Sensor platform for the Fresh-r integration."""

from __future__ import annotations

from pyfreshr.models import DeviceReadings, DeviceType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreshrConfigEntry, FreshrReadingsCoordinator

PARALLEL_UPDATES = 0

_T1 = SensorEntityDescription(
    key="t1",
    translation_key="inside_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)
_T2 = SensorEntityDescription(
    key="t2",
    translation_key="outside_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)
_CO2 = SensorEntityDescription(
    key="co2",
    translation_key="co2",
    device_class=SensorDeviceClass.CO2,
    native_unit_of_measurement="ppm",
)
_HUM = SensorEntityDescription(
    key="hum",
    translation_key="humidity",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=PERCENTAGE,
)
_FLOW = SensorEntityDescription(
    key="flow",
    translation_key="flow",
    native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
)
_DP = SensorEntityDescription(
    key="dp",
    translation_key="dew_point",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    entity_registry_enabled_default=False,
)
_TEMP = SensorEntityDescription(
    key="temp",
    translation_key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
)

SENSOR_TYPES: dict[DeviceType, tuple[SensorEntityDescription, ...]] = {
    DeviceType.FRESH_R: (_T1, _T2, _CO2, _HUM, _FLOW, _DP),
    DeviceType.FORWARD: (_T1, _T2, _CO2, _HUM, _FLOW, _DP, _TEMP),
    DeviceType.MONITOR: (_CO2, _HUM, _DP, _TEMP),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FreshrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fresh-r sensors from a config entry."""
    devices_coordinator = config_entry.runtime_data.devices
    readings_coordinator = config_entry.runtime_data.readings
    known_device_ids: set[str] = set()

    def _async_add_new_devices() -> None:
        """Add sensors for new devices and remove entries for stale devices."""
        current_device_ids: set[str] = set()
        if devices_coordinator.data:
            device_map = {d.id: d for d in devices_coordinator.data if d.id}
            current_device_ids = set(device_map)

            new_device_ids = current_device_ids - known_device_ids
            if new_device_ids:
                known_device_ids.update(new_device_ids)
                entities: list[FreshrSensor] = []
                for device_id in new_device_ids:
                    device_summary = device_map[device_id]
                    descriptions = SENSOR_TYPES.get(
                        device_summary.device_type, SENSOR_TYPES[DeviceType.FRESH_R]
                    )
                    device_info = DeviceInfo(
                        identifiers={(DOMAIN, device_id)},
                        name=device_id,
                        manufacturer="Fresh-r",
                    )
                    entities.extend(
                        FreshrSensor(
                            readings_coordinator, device_id, description, device_info
                        )
                        for description in descriptions
                    )
                async_add_entities(entities)

        stale_device_ids = known_device_ids - current_device_ids
        if stale_device_ids:
            registry = dr.async_get(hass)
            for device_id in stale_device_ids:
                if device_entry := registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                ):
                    registry.async_update_device(
                        device_entry.id,
                        remove_config_entry_id=config_entry.entry_id,
                    )
            known_device_ids.difference_update(stale_device_ids)

    config_entry.async_on_unload(
        devices_coordinator.async_add_listener(_async_add_new_devices)
    )
    _async_add_new_devices()


class FreshrSensor(CoordinatorEntity[FreshrReadingsCoordinator], SensorEntity):
    """Representation of a Fresh-r sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: FreshrReadingsCoordinator,
        device_id: str,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_device_info = device_info
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the value from coordinator data."""
        device_current: DeviceReadings | None = self.coordinator.data.get(
            self._device_id
        )
        if device_current is None:
            return None

        value = getattr(device_current, self.entity_description.key, None)
        if value is None:
            return None

        if self.entity_description.key in ("t1", "t2", "dp", "temp", "flow"):
            return float(value)
        if self.entity_description.key in ("co2", "hum"):
            return int(value)
        return None
