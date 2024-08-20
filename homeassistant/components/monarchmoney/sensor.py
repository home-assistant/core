"""Sensor config - monarch money."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MonarchMoneyConfigEntry
from .entity import MonarchMoneyAccountEntity, MonarchMoneyCashFlowEntity


@dataclass(frozen=True, kw_only=True)
class MonarchMoneySensorEntityDescription(SensorEntityDescription):
    """Describe a sensor entity."""

    value_fn: Callable[[Any], StateType]
    picture_fn: Callable[[Any], str] | None = None


MONARCH_MONEY_VALUE_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="value",
        translation_key="value",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        picture_fn=lambda account: account.logo_url,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

MONARCH_MONEY_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="currentBalance",
        translation_key="balance",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account.balance,
        picture_fn=lambda account: account.logo_url,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

MONARCH_MONEY_AGE_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="age",
        translation_key="age",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: account.last_update,
    ),
    MonarchMoneySensorEntityDescription(
        key="created",
        translation_key="created",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: account.date_created,
    ),
)

MONARCH_CASHFLOW_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="sum_income",
        translation_key="sum_income",
        value_fn=lambda summary: summary["sumIncome"],
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        icon="mdi:cash-plus",
    ),
    MonarchMoneySensorEntityDescription(
        key="sum_expense",
        translation_key="sum_expense",
        value_fn=lambda summary: summary["sumExpense"],
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        icon="mdi:cash-minus",
    ),
    MonarchMoneySensorEntityDescription(
        key="savings",
        translation_key="savings",
        value_fn=lambda summary: summary["savings"],
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_DOLLAR,
        icon="mdi:piggy-bank-outline",
    ),
    MonarchMoneySensorEntityDescription(
        key="savings_rate",
        translation_key="savings_rate",
        value_fn=lambda summary: summary["savingsRate"] * 100,
        suggested_display_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cash-sync",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonarchMoneyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monarch Money sensors for config entries."""
    mm_coordinator = config_entry.runtime_data

    entity_list = (
        [
            MonarchMoneyCashFlowSensor(
                mm_coordinator,
                sensor_description,
                mm_coordinator.cashflow_summary,
            )
            for sensor_description in MONARCH_CASHFLOW_SENSORS
        ]
        + [
            MonarchMoneySensor(
                mm_coordinator,
                sensor_description,
                account,
            )
            for account in mm_coordinator.balance_accounts
            for sensor_description in MONARCH_MONEY_SENSORS
        ]
        + [
            MonarchMoneySensor(
                mm_coordinator,
                sensor_description,
                account,
            )
            for account in mm_coordinator.accounts
            for sensor_description in MONARCH_MONEY_AGE_SENSORS
        ]
        + [
            MonarchMoneySensor(
                mm_coordinator,
                sensor_description,
                account,
            )
            for account in mm_coordinator.value_accounts
            for sensor_description in MONARCH_MONEY_VALUE_SENSORS
        ]
    )

    async_add_entities(entity_list)


class MonarchMoneyCashFlowSensor(MonarchMoneyCashFlowEntity, SensorEntity):
    """Cashflow summary sensor."""

    entity_description: MonarchMoneySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state."""
        return self.entity_description.value_fn(self.summary_data)


class MonarchMoneySensor(MonarchMoneyAccountEntity, SensorEntity):
    """Define a monarch money sensor."""

    entity_description: MonarchMoneySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state."""
        return self.entity_description.value_fn(self.account_data)

    @property
    def entity_picture(self) -> str | None:
        """Return the picture of the account as provided by monarch money if it exists."""
        if self.entity_description.picture_fn is not None:
            return self.entity_description.picture_fn(self.account_data)
        return None
