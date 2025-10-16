"""Sensor platform for Firefly III integration."""

from __future__ import annotations

from pyfirefly.models import Account, Category

from homeassistant.components.sensor import SensorEntity, SensorStateClass, StateType
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import FireflyAccountBaseEntity, FireflyCategoryBaseEntity

ACCOUNT_ROLE_MAPPING = {
    "defaultAsset": "default_asset",
    "sharedAsset": "shared_asset",
    "savingAsset": "saving_asset",
    "ccAsset": "cc_asset",
    "cashWalletAsset": "cash_wallet_asset",
}
ACCOUNT_TYPE_ICONS = {
    "expense": "mdi:cash-minus",
    "asset": "mdi:account-cash",
    "revenue": "mdi:cash-plus",
    "liability": "mdi:hand-coin",
}

ACCOUNT_BALANCE = "account_balance"
ACCOUNT_ROLE = "account_role"
ACCOUNT_TYPE = "account_type"
CATEGORY = "category"


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
            FireflyAccountBalanceSensor(coordinator, account, ACCOUNT_BALANCE)
        )
        entities.append(FireflyAccountRoleSensor(coordinator, account, ACCOUNT_ROLE))
        entities.append(FireflyAccountTypeSensor(coordinator, account, ACCOUNT_TYPE))

    entities.extend(
        [
            FireflyCategorySensor(coordinator, category, CATEGORY)
            for category in coordinator.data.category_details
        ]
    )

    async_add_entities(entities)


class FireflyAccountBalanceSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account balance sensor."""

    _attr_translation_key = "account_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        account: Account,
        key: str,
    ) -> None:
        """Initialize the account balance sensor."""
        super().__init__(coordinator, account, key)
        self._account = account
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return current account balance."""
        return self._account.attributes.current_balance


class FireflyAccountRoleSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account role diagnostic sensor."""

    _attr_translation_key = "account_role"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        account: Account,
        key: str,
    ) -> None:
        """Initialize the account role sensor."""
        super().__init__(coordinator, account, key)
        self._account = account

    @property
    def native_value(self) -> StateType:
        """Return account role."""

        # An account can be empty and then should resort to Unknown
        account_role: str | None = self._account.attributes.account_role
        if account_role is None:
            return None

        return ACCOUNT_ROLE_MAPPING.get(account_role, account_role)


class FireflyAccountTypeSensor(FireflyAccountBaseEntity, SensorEntity):
    """Account type diagnostic sensor."""

    _attr_translation_key = "account_type"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        account: Account,
        key: str,
    ) -> None:
        """Initialize the account type sensor."""
        super().__init__(coordinator, account, key)
        acc_type = account.attributes.type
        self._attr_icon = (
            ACCOUNT_TYPE_ICONS.get(acc_type, "mdi:bank")
            if acc_type is not None
            else "mdi:bank"
        )

    @property
    def native_value(self) -> StateType:
        """Return account type."""
        return self._account.attributes.type


class FireflyCategorySensor(FireflyCategoryBaseEntity, SensorEntity):
    """Category sensor."""

    _attr_translation_key = "category"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        category: Category,
        key: str,
    ) -> None:
        """Initialize the category sensor."""
        super().__init__(coordinator, category, key)
        self._category = category
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
