"""Support for the GIOS service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    ATTR_AQI,
    ATTR_C6H6,
    ATTR_CO,
    ATTR_INDEX,
    ATTR_NO2,
    ATTR_O3,
    ATTR_PM10,
    ATTR_PM25,
    ATTR_SO2,
    ATTR_STATION,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    URL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GiosSensorEntityDescription(SensorEntityDescription):
    """Class describing GIOS sensor entities."""

    value: Callable | None = round


SENSOR_TYPES: tuple[GiosSensorEntityDescription, ...] = (
    GiosSensorEntityDescription(
        key=ATTR_AQI,
        name="AQI",
        value=None,
    ),
    GiosSensorEntityDescription(
        key=ATTR_C6H6,
        name="C6H6",
        icon="mdi:molecule",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_CO,
        name="CO",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_NO2,
        name="NO2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_O3,
        name="O3",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM10,
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM25,
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_SO2,
        name="SO2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
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

    sensors: list[GiosSensor | GiosAqiSensor] = []

    for description in SENSOR_TYPES:
        if getattr(coordinator.data, description.key) is None:
            continue
        if description.key == ATTR_AQI:
            sensors.append(GiosAqiSensor(name, coordinator, description))
        else:
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
        self._attr_unique_id = f"{coordinator.gios.station_id}-{description.key}"
        self._attrs: dict[str, Any] = {
            ATTR_STATION: self.coordinator.gios.station_name,
        }
        self.entity_description = description

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        self._attrs[ATTR_NAME] = getattr(
            self.coordinator.data, self.entity_description.key
        ).name
        self._attrs[ATTR_INDEX] = getattr(
            self.coordinator.data, self.entity_description.key
        ).index
        return self._attrs

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        state = getattr(self.coordinator.data, self.entity_description.key).value
        assert self.entity_description.value is not None
        return cast(StateType, self.entity_description.value(state))


class GiosAqiSensor(GiosSensor):
    """Define an GIOS AQI sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key).value
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available
        return available and bool(
            getattr(self.coordinator.data, self.entity_description.key)
        )
