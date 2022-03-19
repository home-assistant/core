"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import COORDINATOR, DOMAIN, NAME, SENSORS

ICON = "mdi:flash"
_LOGGER = logging.getLogger(__name__)


@dataclass
class EnvoyRequiredKeysMixin:
    """Mixin for required keys."""

    value_idx: int


@dataclass
class EnvoySensorEntityDescription(SensorEntityDescription, EnvoyRequiredKeysMixin):
    """Describes an Envoy inverter sensor entity."""


INVERTERS_KEY = "inverters"
LAST_REPORTED_KEY = "last_reported"

INVERTER_SENSORS = (
    EnvoySensorEntityDescription(
        key=INVERTERS_KEY,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_idx=0,
    ),
    EnvoySensorEntityDescription(
        key=LAST_REPORTED_KEY,
        name="Last Reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_idx=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    envoy_name = data[NAME]
    envoy_serial_num = config_entry.unique_id
    envoy_data: dict = coordinator.data
    assert envoy_serial_num is not None
    _LOGGER.debug("Envoy data: %s", envoy_data)

    entities: list[Envoy | EnvoyInverter] = []
    for description in SENSORS:
        data = envoy_data.get(description.key)
        if isinstance(data, str) and "not available" in data:
            continue
        entities.append(
            Envoy(
                coordinator,
                description,
                f"{envoy_name} {description.name}",
                envoy_name,
                envoy_serial_num,
            )
        )

    if production := envoy_data.get("inverters_production"):
        entities.extend(
            EnvoyInverter(
                coordinator,
                description,
                f"{envoy_name} Inverter {inverter} {description.name}".strip(),
                envoy_serial_num,
                str(inverter),
            )
            for description in INVERTER_SENSORS
            for inverter in production
        )

    async_add_entities(entities)


class Envoy(CoordinatorEntity, SensorEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: SensorEntityDescription,
        name: str,
        envoy_name: str,
        envoy_serial_num: str,
    ) -> None:
        """Initialize Envoy entity."""
        self.entity_description = description
        self._attr_name = name
        self._attr_unique_id = f"{envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(envoy_serial_num))},
            manufacturer="Enphase",
            model="Envoy",
            name=envoy_name,
        )
        super().__init__(coordinator)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)


class EnvoyInverter(CoordinatorEntity, SensorEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    entity_description: EnvoySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: EnvoySensorEntityDescription,
        name: str,
        envoy_serial_num: str,
        serial_number: str,
    ) -> None:
        """Initialize Envoy inverter entity."""
        self.entity_description = description
        self._serial_number = serial_number
        self._attr_name = name
        if description.key == INVERTERS_KEY:
            self._attr_unique_id = serial_number
        else:
            self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Enphase",
            model="Inverter",
            via_device=(DOMAIN, str(envoy_serial_num)),
        )
        super().__init__(coordinator)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        production = self.coordinator.data["inverters_production"]
        val = production[self._serial_number][self.entity_description.value_idx]
        if val is not None and self.entity_description.key == LAST_REPORTED_KEY:
            return dt_util.parse_datetime(val)
        return val
