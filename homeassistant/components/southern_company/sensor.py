"""Support for Southern Company sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import southern_company_api

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SouthernCompanyCoordinator


@dataclass
class SouthernCompanyEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[southern_company_api.account.MonthlyUsage], str | float]


@dataclass
class SouthernCompanyEntityDescription(
    SensorEntityDescription, SouthernCompanyEntityDescriptionMixin
):
    """Describes Southern Company sensor entity."""


SENSORS: tuple[SouthernCompanyEntityDescription, ...] = (
    SouthernCompanyEntityDescription(
        key="dollars_to_date",
        name="Monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.dollars_to_date,
    ),
    SouthernCompanyEntityDescription(
        key="total_kwh_used",
        name="Monthly consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_kwh_used,
    ),
    SouthernCompanyEntityDescription(
        key="average_daily_cost",
        name="Average daily cost",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda data: data.average_daily_cost,
    ),
    SouthernCompanyEntityDescription(
        key="average_daily_usage",
        name="Average daily usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.average_daily_usage,
    ),
    SouthernCompanyEntityDescription(
        key="projected_usage_high",
        name="Higher projected monthly usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.projected_usage_high,
    ),
    SouthernCompanyEntityDescription(
        key="projected_usage_low",
        name="Lower projected monthly usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.projected_usage_low,
    ),
    SouthernCompanyEntityDescription(
        key="projected_bill_amount_low",
        name="Lower projected monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.projected_bill_amount_low,
    ),
    SouthernCompanyEntityDescription(
        key="projected_bill_amount_high",
        name="Higher projected monthly cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.projected_bill_amount_high,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Southern Company sensor."""

    coordinator: SouthernCompanyCoordinator = hass.data[DOMAIN][entry.entry_id]
    southern_company_connection = coordinator.api
    entities: list[SouthernCompanySensor] = []
    for account in await southern_company_connection.accounts:
        device = DeviceInfo(
            identifiers={(DOMAIN, account.number)},
            name=f"Account {account.number}",
            manufacturer="Southern Company",
        )
        for sensor in SENSORS:
            entities.append(SouthernCompanySensor(account, coordinator, sensor, device))

    async_add_entities(entities)


class SouthernCompanySensor(
    SensorEntity, CoordinatorEntity[SouthernCompanyCoordinator]
):
    """Representation of a Southern company sensor."""

    def __init__(
        self,
        account: southern_company_api.Account,
        coordinator: SouthernCompanyCoordinator,
        description: SouthernCompanyEntityDescription,
        device: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: SouthernCompanyEntityDescription = description
        self._account = account
        self._attr_unique_id = f"{self._account.number}_{description.key}"
        self._attr_device_info = device
        self._sensor_data = None

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.coordinator.data is not None:
            return self.entity_description.value_fn(
                self.coordinator.data[self._account.number]
            )
        return None
