"""Support for Electric Kiwi sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from electrickiwi_api.model import AccountBalance, Hop

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ACCOUNT_COORDINATOR, ATTRIBUTION, DOMAIN, HOP_COORDINATOR
from .coordinator import (
    ElectricKiwiAccountDataCoordinator,
    ElectricKiwiHOPDataCoordinator,
)

ATTR_EK_HOP_START = "hop_power_start"
ATTR_EK_HOP_END = "hop_power_end"
ATTR_TOTAL_RUNNING_BALANCE = "total_running_balance"
ATTR_TOTAL_CURRENT_BALANCE = "total_account_balance"
ATTR_NEXT_BILLING_DATE = "next_billing_date"
ATTR_HOP_PERCENTAGE = "hop_percentage"


@dataclass(frozen=True)
class ElectricKiwiAccountRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[AccountBalance], float | datetime]


@dataclass(frozen=True)
class ElectricKiwiAccountSensorEntityDescription(
    SensorEntityDescription, ElectricKiwiAccountRequiredKeysMixin
):
    """Describes Electric Kiwi sensor entity."""


ACCOUNT_SENSOR_TYPES: tuple[ElectricKiwiAccountSensorEntityDescription, ...] = (
    ElectricKiwiAccountSensorEntityDescription(
        key=ATTR_TOTAL_RUNNING_BALANCE,
        translation_key="total_running_balance",
        icon="mdi:currency-usd",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        value_func=lambda account_balance: float(account_balance.total_running_balance),
    ),
    ElectricKiwiAccountSensorEntityDescription(
        key=ATTR_TOTAL_CURRENT_BALANCE,
        translation_key="total_current_balance",
        icon="mdi:currency-usd",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        value_func=lambda account_balance: float(account_balance.total_account_balance),
    ),
    ElectricKiwiAccountSensorEntityDescription(
        key=ATTR_NEXT_BILLING_DATE,
        translation_key="next_billing_date",
        icon="mdi:calendar",
        device_class=SensorDeviceClass.DATE,
        value_func=lambda account_balance: datetime.strptime(
            account_balance.next_billing_date, "%Y-%m-%d"
        ),
    ),
    ElectricKiwiAccountSensorEntityDescription(
        key=ATTR_HOP_PERCENTAGE,
        translation_key="hop_power_savings",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_func=lambda account_balance: float(
            account_balance.connections[0].hop_percentage
        ),
    ),
)


@dataclass(frozen=True)
class ElectricKiwiHOPRequiredKeysMixin:
    """Mixin for required HOP keys."""

    value_func: Callable[[Hop], datetime]


@dataclass(frozen=True)
class ElectricKiwiHOPSensorEntityDescription(
    SensorEntityDescription,
    ElectricKiwiHOPRequiredKeysMixin,
):
    """Describes Electric Kiwi HOP sensor entity."""


def _check_and_move_time(hop: Hop, time: str) -> datetime:
    """Return the time a day forward if HOP end_time is in the past."""
    date_time = datetime.combine(
        dt_util.start_of_local_day(),
        datetime.strptime(time, "%I:%M %p").time(),
        dt_util.DEFAULT_TIME_ZONE,
    )

    end_time = datetime.combine(
        dt_util.start_of_local_day(),
        datetime.strptime(hop.end.end_time, "%I:%M %p").time(),
        dt_util.DEFAULT_TIME_ZONE,
    )

    if end_time < dt_util.now():
        return date_time + timedelta(days=1)
    return date_time


HOP_SENSOR_TYPES: tuple[ElectricKiwiHOPSensorEntityDescription, ...] = (
    ElectricKiwiHOPSensorEntityDescription(
        key=ATTR_EK_HOP_START,
        translation_key="hop_free_power_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_func=lambda hop: _check_and_move_time(hop, hop.start.start_time),
    ),
    ElectricKiwiHOPSensorEntityDescription(
        key=ATTR_EK_HOP_END,
        translation_key="hop_free_power_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_func=lambda hop: _check_and_move_time(hop, hop.end.end_time),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Electric Kiwi Sensors Setup."""
    account_coordinator: ElectricKiwiAccountDataCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ][ACCOUNT_COORDINATOR]

    entities: list[SensorEntity] = [
        ElectricKiwiAccountEntity(
            account_coordinator,
            description,
        )
        for description in ACCOUNT_SENSOR_TYPES
    ]

    hop_coordinator: ElectricKiwiHOPDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        HOP_COORDINATOR
    ]
    entities.extend(
        [
            ElectricKiwiHOPEntity(hop_coordinator, description)
            for description in HOP_SENSOR_TYPES
        ]
    )
    async_add_entities(entities)


class ElectricKiwiAccountEntity(
    CoordinatorEntity[ElectricKiwiAccountDataCoordinator], SensorEntity
):
    """Entity object for Electric Kiwi sensor."""

    entity_description: ElectricKiwiAccountSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: ElectricKiwiAccountDataCoordinator,
        description: ElectricKiwiAccountSensorEntityDescription,
    ) -> None:
        """Entity object for Electric Kiwi sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator._ek_api.customer_number}"
            f"_{coordinator._ek_api.connection_id}_{description.key}"
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)


class ElectricKiwiHOPEntity(
    CoordinatorEntity[ElectricKiwiHOPDataCoordinator], SensorEntity
):
    """Entity object for Electric Kiwi sensor."""

    entity_description: ElectricKiwiHOPSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: ElectricKiwiHOPDataCoordinator,
        description: ElectricKiwiHOPSensorEntityDescription,
    ) -> None:
        """Entity object for Electric Kiwi sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator._ek_api.customer_number}"
            f"_{coordinator._ek_api.connection_id}_{description.key}"
        )
        self.entity_description = description

    @property
    def native_value(self) -> datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.coordinator.data)
