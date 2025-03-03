"""Sensor config - monarch money."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from typedmonarchmoney.models import MonarchAccount, MonarchCashflowSummary

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import MonarchMoneyConfigEntry
from .entity import MonarchMoneyAccountEntity, MonarchMoneyCashFlowEntity


@dataclass(frozen=True, kw_only=True)
class MonarchMoneyAccountSensorEntityDescription(SensorEntityDescription):
    """Describe an account sensor entity."""

    value_fn: Callable[[MonarchAccount], StateType | datetime]
    picture_fn: Callable[[MonarchAccount], str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class MonarchMoneyCashflowSensorEntityDescription(SensorEntityDescription):
    """Describe a cashflow sensor entity."""

    summary_fn: Callable[[MonarchCashflowSummary], StateType]


# These sensors include assets like a boat that might have value
MONARCH_MONEY_VALUE_SENSORS: tuple[MonarchMoneyAccountSensorEntityDescription, ...] = (
    MonarchMoneyAccountSensorEntityDescription(
        key="value",
        translation_key="value",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        picture_fn=lambda account: account.logo_url,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

# Most accounts are balance sensors
MONARCH_MONEY_SENSORS: tuple[MonarchMoneyAccountSensorEntityDescription, ...] = (
    MonarchMoneyAccountSensorEntityDescription(
        key="currentBalance",
        translation_key="balance",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        picture_fn=lambda account: account.logo_url,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

MONARCH_MONEY_AGE_SENSORS: tuple[MonarchMoneyAccountSensorEntityDescription, ...] = (
    MonarchMoneyAccountSensorEntityDescription(
        key="age",
        translation_key="age",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: account.last_update,
    ),
)

MONARCH_CASHFLOW_SENSORS: tuple[MonarchMoneyCashflowSensorEntityDescription, ...] = (
    MonarchMoneyCashflowSensorEntityDescription(
        key="sum_income",
        translation_key="sum_income",
        summary_fn=lambda summary: summary.income,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
    MonarchMoneyCashflowSensorEntityDescription(
        key="sum_expense",
        translation_key="sum_expense",
        summary_fn=lambda summary: summary.expenses,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
    MonarchMoneyCashflowSensorEntityDescription(
        key="savings",
        translation_key="savings",
        summary_fn=lambda summary: summary.savings,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
    MonarchMoneyCashflowSensorEntityDescription(
        key="savings_rate",
        translation_key="savings_rate",
        summary_fn=lambda summary: summary.savings_rate * 100,
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonarchMoneyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Monarch Money sensors for config entries."""
    mm_coordinator = config_entry.runtime_data

    entity_list: list[MonarchMoneySensor | MonarchMoneyCashFlowSensor] = [
        MonarchMoneyCashFlowSensor(
            mm_coordinator,
            sensor_description,
        )
        for sensor_description in MONARCH_CASHFLOW_SENSORS
    ]
    entity_list.extend(
        MonarchMoneySensor(
            mm_coordinator,
            sensor_description,
            account,
        )
        for account in mm_coordinator.balance_accounts
        for sensor_description in MONARCH_MONEY_SENSORS
    )
    entity_list.extend(
        MonarchMoneySensor(
            mm_coordinator,
            sensor_description,
            account,
        )
        for account in mm_coordinator.accounts
        for sensor_description in MONARCH_MONEY_AGE_SENSORS
    )
    entity_list.extend(
        MonarchMoneySensor(
            mm_coordinator,
            sensor_description,
            account,
        )
        for account in mm_coordinator.value_accounts
        for sensor_description in MONARCH_MONEY_VALUE_SENSORS
    )

    async_add_entities(entity_list)


class MonarchMoneyCashFlowSensor(MonarchMoneyCashFlowEntity, SensorEntity):
    """Cashflow summary sensor."""

    entity_description: MonarchMoneyCashflowSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.summary_fn(self.summary_data)


class MonarchMoneySensor(MonarchMoneyAccountEntity, SensorEntity):
    """Define a monarch money sensor."""

    entity_description: MonarchMoneyAccountSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.account_data)

    @property
    def entity_picture(self) -> str | None:
        """Return the picture of the account as provided by monarch money if it exists."""
        if self.entity_description.picture_fn is not None:
            return self.entity_description.picture_fn(self.account_data)
        return None
