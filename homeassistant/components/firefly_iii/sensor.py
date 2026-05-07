"""Sensor platform for Firefly III integration."""

from datetime import datetime

from pyfirefly.models import Account, Bill, Budget, Category

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    StateType,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import parse_datetime

from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import (
    FireflyAccountBaseEntity,
    FireflyBillBaseEntity,
    FireflyBudgetBaseEntity,
    FireflyCategoryBaseEntity,
)

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
BUDGET = "budget"
BUDGET_LIMIT = "budget_limit"
BUDGET_REMAINING = "budget_remaining"
SUBSCRIPTION_AMOUNT = "subscription_amount"
SUBSCRIPTION_NEXT_EXPECTED = "subscription_next_expected"
SUBSCRIPTION_LAST_PAID = "subscription_last_paid"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireflyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Firefly III sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for account in coordinator.data.accounts.values():
        entities.append(
            FireflyAccountBalanceSensor(coordinator, account, ACCOUNT_BALANCE)
        )
        entities.append(FireflyAccountRoleSensor(coordinator, account, ACCOUNT_ROLE))
        entities.append(FireflyAccountTypeSensor(coordinator, account, ACCOUNT_TYPE))

    entities.extend(
        [
            FireflyCategorySensor(coordinator, category, CATEGORY)
            for category in coordinator.data.category_details.values()
        ]
    )

    for budget in coordinator.data.budgets.values():
        entities.append(FireflyBudgetSpentSensor(coordinator, budget, BUDGET))
        entities.append(
            FireflyBudgetLimitSensor(coordinator, budget, BUDGET_LIMIT)
        )
        entities.append(
            FireflyBudgetRemainingSensor(coordinator, budget, BUDGET_REMAINING)
        )

    for bill in coordinator.data.bills.values():
        entities.append(
            FireflySubscriptionAmountSensor(coordinator, bill, SUBSCRIPTION_AMOUNT)
        )
        entities.append(
            FireflySubscriptionNextExpectedSensor(
                coordinator, bill, SUBSCRIPTION_NEXT_EXPECTED
            )
        )
        entities.append(
            FireflySubscriptionLastPaidSensor(
                coordinator, bill, SUBSCRIPTION_LAST_PAID
            )
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


class FireflyBudgetSpentSensor(FireflyBudgetBaseEntity, SensorEntity):
    """Budget spent sensor."""

    _attr_translation_key = "budget"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        budget: Budget,
        key: str,
    ) -> None:
        """Initialize the budget sensor."""
        super().__init__(coordinator, budget, key)
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return spent value for this budget in the period."""
        spent_items = self._budget.attributes.spent or []
        return sum(float(item.sum) for item in spent_items if item.sum is not None)


class FireflyBudgetLimitSensor(FireflyBudgetBaseEntity, SensorEntity):
    """Budget limit sensor."""

    _attr_translation_key = "budget_limit"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        budget: Budget,
        key: str,
    ) -> None:
        """Initialize the budget limit sensor."""
        super().__init__(coordinator, budget, key)
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return the budget limit amount for the current period."""
        limits = self.coordinator.data.budget_limits.get(self._budget_id, [])
        if limits:
            total = sum(
                float(limit.amount)
                for limit in limits
                if limit.amount is not None
            )
            return total
        auto_amount = self._budget.attributes.auto_budget_amount
        if auto_amount is not None:
            return float(auto_amount)
        return None


class FireflyBudgetRemainingSensor(FireflyBudgetBaseEntity, SensorEntity):
    """Budget remaining sensor."""

    _attr_translation_key = "budget_remaining"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        budget: Budget,
        key: str,
    ) -> None:
        """Initialize the budget remaining sensor."""
        super().__init__(coordinator, budget, key)
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return the remaining budget (limit - spent)."""
        limits = self.coordinator.data.budget_limits.get(self._budget_id, [])
        if limits:
            limit_total = sum(
                float(limit.amount)
                for limit in limits
                if limit.amount is not None
            )
        else:
            auto_amount = self._budget.attributes.auto_budget_amount
            if auto_amount is None:
                return None
            limit_total = float(auto_amount)

        spent_items = self._budget.attributes.spent or []
        spent = sum(float(item.sum) for item in spent_items if item.sum is not None)
        return limit_total - spent


class FireflySubscriptionAmountSensor(FireflyBillBaseEntity, SensorEntity):
    """Subscription expected amount sensor."""

    _attr_translation_key = "subscription_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        bill: Bill,
        key: str,
    ) -> None:
        """Initialize the subscription amount sensor."""
        super().__init__(coordinator, bill, key)
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )

    @property
    def native_value(self) -> StateType:
        """Return the expected subscription amount (average of min and max)."""
        attrs = self._bill.attributes
        if attrs.amount_min is not None and attrs.amount_max is not None:
            return (float(attrs.amount_min) + float(attrs.amount_max)) / 2
        if attrs.amount_min is not None:
            return float(attrs.amount_min)
        if attrs.amount_max is not None:
            return float(attrs.amount_max)
        return None


class FireflySubscriptionNextExpectedSensor(FireflyBillBaseEntity, SensorEntity):
    """Subscription next expected match sensor."""

    _attr_translation_key = "subscription_next_expected"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the next expected match date."""
        value = self._bill.attributes.next_expected_match
        if value is None:
            return None
        return parse_datetime(value)


class FireflySubscriptionLastPaidSensor(FireflyBillBaseEntity, SensorEntity):
    """Subscription last paid sensor."""

    _attr_translation_key = "subscription_last_paid"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the last paid date."""
        paid_dates = self._bill.attributes.paid_dates
        if paid_dates and paid_dates[-1].date:
            return parse_datetime(paid_dates[-1].date)
        return None
