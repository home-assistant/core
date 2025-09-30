"""Sensor platform for Firefly III integration."""

from __future__ import annotations

from pyfirefly.models import Account, Category

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import FireflyAccountBaseEntity, FireflyBaseEntity

ACCOUNT_BALANCE_DESCRIPTION = SensorEntityDescription(
    key="account_balance",
    translation_key="account_balance",
    device_class=SensorDeviceClass.MONETARY,
    state_class=SensorStateClass.TOTAL,
)
ACCOUNT_ROLE_DESCRIPTION = SensorEntityDescription(
    key="account_role",
    translation_key="account_role",
)
ACCOUNT_TYPE_DESCRIPTION = SensorEntityDescription(
    key="account_type",
    translation_key="account_type",
)

CATEGORY_DESCRIPTION = SensorEntityDescription(
    key="category",
    translation_key="category",
    device_class=SensorDeviceClass.MONETARY,
    state_class=SensorStateClass.TOTAL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireflyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Firefly III sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for account in coordinator.data.accounts:
        entities.append(
            FireflyAccountBalanceSensor(
                coordinator, ACCOUNT_BALANCE_DESCRIPTION, account
            )
        )
        entities.append(
            FireflyAccountRoleSensor(coordinator, ACCOUNT_ROLE_DESCRIPTION, account)
        )
        entities.append(
            FireflyAccountTypeSensor(coordinator, ACCOUNT_TYPE_DESCRIPTION, account)
        )

    entities.extend(
        [
            FireflyCategorySensor(coordinator, CATEGORY_DESCRIPTION, category)
            for category in coordinator.data.category_details
        ]
    )

    async_add_entities(entities)


class FireflyAccountBalanceSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account balance sensor."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize the account balance sensor."""
        super().__init__(coordinator, description, account)
        self._account = account
        self._attr_name = f"{account.attributes.name}"
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{account.id}_{description.key}"
        )
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )
        acc_type = account.attributes.type
        if acc_type == "expense":
            self._attr_icon = "mdi:cash-minus"
        elif acc_type == "asset":
            self._attr_icon = "mdi:account-cash"
        elif acc_type == "revenue":
            self._attr_icon = "mdi:cash-plus"
        elif acc_type == "liability":
            self._attr_icon = "mdi:hand-coin"
        else:
            self._attr_icon = "mdi:bank"

    @property
    def native_value(self) -> str | None:
        """Return current account balance."""
        return self._account.attributes.current_balance


class FireflyAccountRoleSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account role diagnostic sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "account_role"

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize the account role sensor."""
        super().__init__(
            coordinator,
            SensorEntityDescription(key="account_role", translation_key="account_role"),
            account,
        )
        self._account = account
        self._attr_name = account.attributes.account_role
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{account.id}_{description.key}"
        )

    @property
    def native_value(self) -> str | None:
        """Return account role."""
        return self._account.attributes.account_role or None


class FireflyAccountTypeSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account type diagnostic sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "account_type"

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize the account type sensor."""
        super().__init__(
            coordinator,
            SensorEntityDescription(key="account_type", translation_key="account_type"),
            account,
        )
        self._account = account
        self._attr_name = account.attributes.type
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{account.id}_{description.key}"
        )

    @property
    def native_value(self) -> str | None:
        """Return account type."""
        return self._account.attributes.type or None


class FireflyCategorySensor(FireflyBaseEntity, SensorEntity):
    """Category aggregate monetary sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "category"

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        category: Category,
    ) -> None:
        """Initialize the category sensor."""
        super().__init__(coordinator, description)
        self._category = category
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{description.key}_{category.id}"
        )
        self._attr_name = category.attributes.name
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> float | None:
        """Return net spent+earned value for this category in the period."""
        spent_items = self._category.attributes.spent or []
        earned_items = self._category.attributes.earned or []
        spent = sum(float(item.sum) for item in spent_items if item.sum is not None)
        earned = sum(float(item.sum) for item in earned_items if item.sum is not None)
        if spent == 0 and earned == 0:
            return None
        return spent + earned
