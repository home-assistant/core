"""Sensor platform for Family Safety."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pyfamilysafety import Account

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FamilySafetyConfigEntry, FamilySafetyCoordinator
from .entity import FamilySafetyDevice

# handled by coordinator and callbacks
PARALLEL_UPDATES = 0


class FamilySafetySensor(StrEnum):
    """Store keys for Family Safety sensors."""

    PENDING_REQUESTS = "pending_requests"
    PLAYING_TIME = "playing_time"
    ACCOUNT_BALANCE = "account_balance"


@dataclass(kw_only=True, frozen=True)
class FamilySafetySensorEntityDescription(SensorEntityDescription):
    """Describes Family Safety sensor entities."""

    native_unit_of_measurement_fn: Callable[[FamilySafetyDevice], str] | None = None
    value_fn: Callable[[FamilySafetyDevice], int | float | None]


SENSOR_DESCRIPTIONS: tuple[FamilySafetySensorEntityDescription, ...] = (
    FamilySafetySensorEntityDescription(
        key=FamilySafetySensor.PLAYING_TIME,
        translation_key=FamilySafetySensor.PLAYING_TIME,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: device.account.today_screentime_usage / 1000 / 60,
    ),
    FamilySafetySensorEntityDescription(
        key=FamilySafetySensor.ACCOUNT_BALANCE,
        translation_key=FamilySafetySensor.ACCOUNT_BALANCE,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda device: device.account.account_balance,
        native_unit_of_measurement_fn=lambda device: device.account.account_currency,
        suggested_display_precision=2,
    ),
    FamilySafetySensorEntityDescription(
        key=FamilySafetySensor.PENDING_REQUESTS,
        translation_key=FamilySafetySensor.PENDING_REQUESTS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: len(
            device.coordinator.api.get_account_requests(device.account.user_id)
        ),
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FamilySafetyConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Family Safety sensors."""
    async_add_devices(
        FamilySafetySensorEntity(
            coordinator=entry.runtime_data,
            account=account,
            description=description,
        )
        for account in entry.runtime_data.api.accounts
        for description in SENSOR_DESCRIPTIONS
    )


class FamilySafetySensorEntity(FamilySafetyDevice, SensorEntity):
    """Representation of a Family Safety sensor."""

    def __init__(
        self,
        coordinator: FamilySafetyCoordinator,
        account: Account,
        description: FamilySafetySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, account=account, key=description.key)
        self.entity_description: FamilySafetySensorEntityDescription = description

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.entity_description.value_fn(self)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        if self.entity_description.native_unit_of_measurement_fn is None:
            return self.entity_description.native_unit_of_measurement
        return self.entity_description.native_unit_of_measurement_fn(self)
