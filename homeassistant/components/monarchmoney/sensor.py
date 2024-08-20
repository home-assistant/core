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
from .const import LOGGER
from .entity import MonarchMoneyAccountEntity, MonarchMoneyCashFlowEntity


def _type_to_icon(account: Any) -> str:
    """Return icon mappings - in the case that an account does not have a "logoURL" set - this is a subset of the 86 possible combos."""
    account_type = account["type"]["name"]
    account_subtype = account["subtype"]["name"]

    icon_mapping = {
        "brokerage": {
            "brokerage": "mdi:chart-line",
            "cryptocurrency": "mdi:currency-btc",
            "ira": "mdi:bank",
            "st_401a": "mdi:chart-bell-curve-cumulative",
            "st_403b": "mdi:chart-bell-curve-cumulative",
            "st_529": "mdi:school-outline",
        },
        "vehicle": {
            "car": "mdi:car",
            "boat": "mdi:sail-boat",
            "motorcycle": "mdi:motorbike",
            "snowmobile": "mdi:snowmobile",
            "bicycle": "mdi:bicycle",
            "other": "mdi:car",
        },
        "credit": {"credit_card": "mdi:credit-card"},
        "depository": {
            "cash_management": "mdi:cash",
            "checking": "mdi:checkbook",
            "savings": "mdi:piggy-bank-outline",
            "money_market": "mdi:piggy-bank-outline",
        },
        "loan": {
            "line_of_credit": "mdi:credit-card-plus",
            "loan": "mdi:bank-outline",
            "mortgage": "mdi:home-city-outline",
        },
    }

    default_icons = {
        "brokerage": "mdi:chart-line",
        "credit": "mdi:credit-card",
        "depository": "mdi:cash",
        "loan": "mdi:bank-outline",
        "vehicle": "mdi:car",
    }
    if account_subtype not in icon_mapping.get(account_type, {}):
        LOGGER.debug(
            f"Unknown subtype '{account_subtype}' for account type '{account_type}'"
        )
        return default_icons.get(account_type, "mdi:cash")

    account_type_icons = icon_mapping.get(account_type, {})
    return account_type_icons.get(
        account_subtype, default_icons.get(account_type, "mdi:help")
    )


@dataclass(frozen=True, kw_only=True)
class MonarchMoneySensorEntityDescription(SensorEntityDescription):
    """Describe a sensor entity."""

    value_fn: Callable[[Any], StateType | datetime]
    picture_fn: Callable[[Any], str] | None = None
    icon_fn: Callable[[Any], str] | None = None


MONARCH_MONEY_VALUE_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="value",
        translation_key="value",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account["currentBalance"],
        picture_fn=lambda account: account["logoUrl"],
        icon_fn=_type_to_icon,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

MONARCH_MONEY_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="currentBalance",
        translation_key="balance",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda account: account["currentBalance"],
        picture_fn=lambda account: account["logoUrl"],
        icon_fn=_type_to_icon,
        native_unit_of_measurement=CURRENCY_DOLLAR,
    ),
)

MONARCH_MONEY_AGE_SENSORS: tuple[MonarchMoneySensorEntityDescription, ...] = (
    MonarchMoneySensorEntityDescription(
        key="age",
        translation_key="age",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: datetime.fromisoformat(account["updatedAt"]),
    ),
    MonarchMoneySensorEntityDescription(
        key="created",
        translation_key="created",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda account: datetime.fromisoformat(account["createdAt"]),
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

    @property
    def icon(self) -> str | None:
        """Icon function."""
        if self.entity_description.icon_fn is not None:
            return self.entity_description.icon_fn(self.account_data)
        return None
