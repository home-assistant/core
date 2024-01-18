"""Support for the GIOS service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from gios.model import GiosSensors

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    ATTR_AQI,
    ATTR_C6H6,
    ATTR_CO,
    ATTR_NO2,
    ATTR_O3,
    ATTR_PM10,
    ATTR_PM25,
    ATTR_SO2,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GiosSensorEntityDescription(SensorEntityDescription):
    """Class describing GIOS sensor entities."""

    value: Callable[[GiosSensors], StateType]
    subkey: str | None = None


SENSOR_TYPES: tuple[GiosSensorEntityDescription, ...] = (
    GiosSensorEntityDescription(
        key=ATTR_AQI,
        value=lambda sensors: sensors.aqi.value if sensors.aqi else None,
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="aqi",
    ),
    GiosSensorEntityDescription(
        key=ATTR_C6H6,
        value=lambda sensors: sensors.c6h6.value if sensors.c6h6 else None,
        suggested_display_precision=0,
        icon="mdi:molecule",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="c6h6",
    ),
    GiosSensorEntityDescription(
        key=ATTR_CO,
        value=lambda sensors: sensors.co.value if sensors.co else None,
        suggested_display_precision=0,
        icon="mdi:molecule",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="co",
    ),
    GiosSensorEntityDescription(
        key=ATTR_NO2,
        value=lambda sensors: sensors.no2.value if sensors.no2 else None,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_NO2,
        subkey="index",
        value=lambda sensors: sensors.no2.index if sensors.no2 else None,
        icon="mdi:molecule",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="no2_index",
    ),
    GiosSensorEntityDescription(
        key=ATTR_O3,
        value=lambda sensors: sensors.o3.value if sensors.o3 else None,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_O3,
        subkey="index",
        value=lambda sensors: sensors.o3.index if sensors.o3 else None,
        icon="mdi:molecule",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="o3_index",
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM10,
        value=lambda sensors: sensors.pm10.value if sensors.pm10 else None,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM10,
        subkey="index",
        value=lambda sensors: sensors.pm10.index if sensors.pm10 else None,
        icon="mdi:molecule",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="pm10_index",
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM25,
        value=lambda sensors: sensors.pm25.value if sensors.pm25 else None,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM25,
        subkey="index",
        value=lambda sensors: sensors.pm25.index if sensors.pm25 else None,
        icon="mdi:molecule",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="pm25_index",
    ),
    GiosSensorEntityDescription(
        key=ATTR_SO2,
        value=lambda sensors: sensors.so2.value if sensors.so2 else None,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_SO2,
        subkey="index",
        value=lambda sensors: sensors.so2.index if sensors.so2 else None,
        icon="mdi:molecule",
        device_class=SensorDeviceClass.ENUM,
        options=["very_bad", "bad", "sufficient", "moderate", "good", "very_good"],
        translation_key="so2_index",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a GIOS entities from a config_entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of one sensor, it is necessary to migrate
    # the unique_id to the new name.
    entity_registry = er.async_get(hass)
    old_unique_id = f"{coordinator.gios.station_id}-pm2.5"
    if entity_id := entity_registry.async_get_entity_id(
        PLATFORM, DOMAIN, old_unique_id
    ):
        new_unique_id = f"{coordinator.gios.station_id}-{ATTR_PM25}"
        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    sensors: list[GiosSensor] = []

    for description in SENSOR_TYPES:
        if getattr(coordinator.data, description.key) is None:
            continue
        sensors.append(GiosSensor(name, coordinator, description))

    async_add_entities(sensors)


class GiosSensor(CoordinatorEntity[GiosDataUpdateCoordinator], SensorEntity):
    """Define an GIOS sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: GiosSensorEntityDescription

    def __init__(
        self,
        name: str,
        coordinator: GiosDataUpdateCoordinator,
        description: GiosSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(coordinator.gios.station_id))},
            manufacturer=MANUFACTURER,
            name=name,
            configuration_url=URL.format(station_id=coordinator.gios.station_id),
        )
        if description.subkey:
            self._attr_unique_id = (
                f"{coordinator.gios.station_id}-{description.key}-{description.subkey}"
            )
        else:
            self._attr_unique_id = f"{coordinator.gios.station_id}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available
        sensor_data = getattr(self.coordinator.data, self.entity_description.key)

        # Sometimes the API returns sensor data without indexes
        if self.entity_description.subkey:
            return available and bool(sensor_data.index)

        return available and bool(sensor_data)
