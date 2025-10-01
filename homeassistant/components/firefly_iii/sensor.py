"""Sensor platform for Firefly III integration."""

from __future__ import annotations

from pyfirefly.models import Account, Category

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import FireflyAccountBaseEntity, FireflyCategoryBaseEntity

ACCOUNT_BALANCE_DESCRIPTION = SensorEntityDescription(
    key="account_balance",
    translation_key="account_balance",
    device_class=SensorDeviceClass.MONETARY,
    state_class=SensorStateClass.TOTAL,
)
ACCOUNT_ROLE_DESCRIPTION = SensorEntityDescription(
    key="account_role",
    translation_key="account_role",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=True,
)
ACCOUNT_TYPE_DESCRIPTION = SensorEntityDescription(
    key="account_type",
    translation_key="account_type",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=True,
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
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_account_{account.id}_{description.key}"
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return current account balance."""
        return self._account.attributes.current_balance


class FireflyAccountRoleSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account role diagnostic sensor."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize the account role sensor."""
        super().__init__(coordinator, description, account)
        self._account = account
        self._attr_icon = "mdi:account-circle"
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_account_{account.id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return account role."""
        # Mapping is needed for translation keys
        mapping = {
            "defaultAsset": "default_asset",
            "sharedAsset": "shared_asset",
            "savingAsset": "saving_asset",
            "ccAsset": "cc_asset",
            "cashWalletAsset": "cash_wallet_asset",
        }
        # An account can be empty and then should resort to Unknown
        account_role: str | None = self._account.attributes.account_role
        if account_role is None:
            return None

        return mapping.get(account_role, account_role)


class FireflyAccountTypeSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account type diagnostic sensor."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        account: Account,
    ) -> None:
        """Initialize the account type sensor."""
        super().__init__(coordinator, description, account)
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

        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_account_{account.id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return account type."""
        return self._account.attributes.type


class FireflyCategorySensor(FireflyCategoryBaseEntity, SensorEntity):
    """Category sensor."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        description: SensorEntityDescription,
        category: Category,
    ) -> None:
        """Initialize the category sensor."""
        super().__init__(coordinator, description, category)
        self._category = category
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_category_{category.id}_{description.key}"
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return net spent+earned value for this category in the period."""
        spent_items = self._category.attributes.spent or []
        earned_items = self._category.attributes.earned or []
        spent = sum(float(item.sum) for item in spent_items if item.sum is not None)
        earned = sum(float(item.sum) for item in earned_items if item.sum is not None)
        if spent == 0 and earned == 0:
            return None
        return spent + earned
