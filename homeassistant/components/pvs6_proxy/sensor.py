"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PVOutputDataUpdateCoordinator
from .interface import Devices


@dataclass
class PVOutputSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Devices], int | float]


@dataclass
class PVOutputSensorEntityDescription(
    SensorEntityDescription, PVOutputSensorEntityDescriptionMixin
):
    """Describes a PVOutput sensor entity."""


SENSORS: tuple[PVOutputSensorEntityDescription, ...] = (
    PVOutputSensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda devices: devices.power_meter_c.p_3phsum_kw,
    ),
    PVOutputSensorEntityDescription(
        key="power_generation",
        translation_key="power_generation",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda devices: devices.power_meter_p.p_3phsum_kw,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a PVOutput sensors based on a config entry."""
    coordinator: PVOutputDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    devices = await coordinator.pvoutput.devices()

    async_add_entities(
        PVOutputSensorEntity(
            coordinator=coordinator,
            description=description,
            system_id="SystemID",
            devices=devices,
        )
        for description in SENSORS
    )


class PVOutputSensorEntity(
    CoordinatorEntity[PVOutputDataUpdateCoordinator], SensorEntity
):
    """Representation of a PVOutput sensor."""

    entity_description: PVOutputSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: PVOutputDataUpdateCoordinator,
        description: PVOutputSensorEntityDescription,
        system_id: str,
        devices: Devices,
    ) -> None:
        """Initialize a PVOutput sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=f"https://pvoutput.org/list.jsp?sid={system_id}",
            identifiers={(DOMAIN, str(system_id))},
            manufacturer="PVOutput",
            model="PVS6",
            name=None,
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
