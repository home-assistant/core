"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import cast

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

INVERTERS_KEY = "inverters"
LAST_REPORTED_KEY = "last_reported"


@dataclass
class EnvoyRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[tuple[float, str]], datetime.datetime | float | None]


@dataclass
class EnvoySensorEntityDescription(SensorEntityDescription, EnvoyRequiredKeysMixin):
    """Describes an Envoy inverter sensor entity."""


def _inverter_last_report_time(
    watt_report_time: tuple[float, str]
) -> datetime.datetime | None:
    if (report_time := watt_report_time[1]) is None:
        return None
    if (last_reported_dt := dt_util.parse_datetime(report_time)) is None:
        return None
    if last_reported_dt.tzinfo is None:
        return last_reported_dt.replace(tzinfo=dt_util.UTC)
    return last_reported_dt


INVERTER_SENSORS = (
    EnvoySensorEntityDescription(
        key=INVERTERS_KEY,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda watt_report_time: watt_report_time[0],
    ),
    EnvoySensorEntityDescription(
        key=LAST_REPORTED_KEY,
        name="Last Reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=_inverter_last_report_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    data: dict = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DataUpdateCoordinator = data[COORDINATOR]
    envoy_data: dict = coordinator.data
    envoy_name: str = data[NAME]
    envoy_serial_num = config_entry.unique_id
    assert envoy_serial_num is not None
    _LOGGER.debug("Envoy data: %s", envoy_data)

    entities: list[Envoy | EnvoyInverter] = []
    for description in SENSORS:
        sensor_data = envoy_data.get(description.key)
        if isinstance(sensor_data, str) and "not available" in sensor_data:
            continue
        entities.append(
            Envoy(
                coordinator,
                description,
                envoy_name,
                envoy_serial_num,
            )
        )

    if production := envoy_data.get("inverters_production"):
        entities.extend(
            EnvoyInverter(
                coordinator,
                description,
                envoy_name,
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
        envoy_name: str,
        envoy_serial_num: str,
    ) -> None:
        """Initialize Envoy entity."""
        self.entity_description = description
        self._attr_name = f"{envoy_name} {description.name}"
        self._attr_unique_id = f"{envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, envoy_serial_num)},
            manufacturer="Enphase",
            model="Envoy",
            name=envoy_name,
        )
        super().__init__(coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (value := self.coordinator.data.get(self.entity_description.key)) is None:
            return None
        return cast(float, value)


class EnvoyInverter(CoordinatorEntity, SensorEntity):
    """Envoy inverter entity."""

    _attr_icon = ICON
    entity_description: EnvoySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: EnvoySensorEntityDescription,
        envoy_name: str,
        envoy_serial_num: str,
        serial_number: str,
    ) -> None:
        """Initialize Envoy inverter entity."""
        self.entity_description = description
        self._serial_number = serial_number
        if description.name:
            self._attr_name = (
                f"{envoy_name} Inverter {serial_number} {description.name}"
            )
        else:
            self._attr_name = f"{envoy_name} Inverter {serial_number}"
        if description.key == INVERTERS_KEY:
            self._attr_unique_id = serial_number
        else:
            self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=f"Inverter {serial_number}",
            manufacturer="Enphase",
            model="Inverter",
            via_device=(DOMAIN, envoy_serial_num),
        )
        super().__init__(coordinator)

    @property
    def native_value(self) -> datetime.datetime | float | None:
        """Return the state of the sensor."""
        watt_report_time: tuple[float, str] = self.coordinator.data[
            "inverters_production"
        ][self._serial_number]
        return self.entity_description.value_fn(watt_report_time)
