"""Sensor platform for Firefly III integration."""

from datetime import UTC, datetime
from typing import Any

from pyfirefly.models import Account, Bill, Budget, Category
from yarl import URL

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    StateType,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import FireflyConfigEntry, FireflyDataUpdateCoordinator
from .entity import (
    FireflyAccountBaseEntity,
    FireflyBaseEntity,
    FireflyBillBaseEntity,
    FireflyBudgetBaseEntity,
    FireflyCategoryBaseEntity,
)

ACCOUNT_ROLE_MAPPING = {
    "defaultAsset": "Default asset",
    "sharedAsset": "Shared asset",
    "savingAsset": "Saving asset",
    "ccAsset": "Credit card asset",
    "cashWalletAsset": "Cash wallet asset",
}

ACCOUNT_BALANCE = "account_balance"
CATEGORY = "category"
BUDGET = "budget"
BUDGET_LIMIT = "budget_limit"
BUDGET_REMAINING = "budget_remaining"
SUBSCRIPTION_AMOUNT = "subscription_amount"
SUBSCRIPTION_NEXT_EXPECTED = "subscription_next_expected"
SUBSCRIPTION_LAST_PAID = "subscription_last_paid"
SUBSCRIPTION_TOTAL_EXPECTED = "subscription_total_expected"
SUBSCRIPTION_ALREADY_PAID = "subscription_already_paid"


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

    entities.append(
        FireflySubscriptionTotalExpectedSensor(coordinator, SUBSCRIPTION_TOTAL_EXPECTED)
    )
    entities.append(
        FireflySubscriptionAlreadyPaidSensor(coordinator, SUBSCRIPTION_ALREADY_PAID)
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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return account role and type as attributes."""
        attrs = self._account.attributes
        account_role = attrs.account_role
        role_display = (
            ACCOUNT_ROLE_MAPPING.get(account_role, account_role)
            if account_role
            else None
        )
        return {
            "account_role": role_display,
            "account_type": attrs.type,
        }


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
                float(limit.amount or limit.native_amount or 0)
                for limit in limits
            )
            if total:
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
        """Return the remaining budget (limit + spent, since spent is negative)."""
        limits = self.coordinator.data.budget_limits.get(self._budget_id, [])
        limit_total = 0.0
        if limits:
            limit_total = sum(
                float(limit.amount or limit.native_amount or 0)
                for limit in limits
            )
        if not limit_total:
            auto_amount = self._budget.attributes.auto_budget_amount
            if auto_amount is None:
                return None
            limit_total = float(auto_amount)

        spent_items = self._budget.attributes.spent or []
        spent = sum(float(item.sum) for item in spent_items if item.sum is not None)
        return limit_total + spent


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
        """Return the next expected match date (first future pay_date or next_expected_match)."""
        now = datetime.now(tz=UTC)
        pay_dates = self._bill.attributes.pay_dates
        if pay_dates:
            for date_str in pay_dates:
                dt = _parse_timestamp(date_str)
                if dt and dt >= now:
                    return dt

        value = self._bill.attributes.next_expected_match
        if not value:
            return None
        return _parse_timestamp(value)


class FireflySubscriptionLastPaidSensor(FireflyBillBaseEntity, SensorEntity):
    """Subscription last paid sensor."""

    _attr_translation_key = "subscription_last_paid"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the last paid date."""
        paid_dates = self._bill.attributes.paid_dates
        if paid_dates and paid_dates[-1].date:
            return _parse_timestamp(paid_dates[-1].date)
        return None


class FireflySubscriptionTotalExpectedSensor(FireflyBaseEntity, SensorEntity):
    """Subscription total expected amount sensor (aggregate across all active bills)."""

    _attr_translation_key = "subscription_total_expected"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the subscription total expected sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_subscriptions_total_expected"
        )
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name="Subscriptions",
            configuration_url=f"{URL(coordinator.config_entry.data[CONF_URL])}/subscriptions",
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_subscriptions")
            },
        )

    @property
    def native_value(self) -> StateType:
        """Return the total expected amount for bills due this month."""
        now = datetime.now(tz=UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            month_end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            month_end = now.replace(month=now.month + 1, day=1)
        total = 0.0
        for bill in self.coordinator.data.bills.values():
            attrs = bill.attributes
            if not attrs.active:
                continue
            pay_dates = attrs.pay_dates
            if pay_dates and any(
                _parse_timestamp(d) and month_start <= _parse_timestamp(d) < month_end
                for d in pay_dates
            ):
                if attrs.amount_min is not None and attrs.amount_max is not None:
                    total += (float(attrs.amount_min) + float(attrs.amount_max)) / 2
                elif attrs.amount_min is not None:
                    total += float(attrs.amount_min)
                elif attrs.amount_max is not None:
                    total += float(attrs.amount_max)
        return total


class FireflySubscriptionAlreadyPaidSensor(FireflyBaseEntity, SensorEntity):
    """Subscription already paid sensor (aggregate of paid bills this period)."""

    _attr_translation_key = "subscription_already_paid"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the subscription already paid sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_subscriptions_already_paid"
        )
        self._attr_native_unit_of_measurement = (
            coordinator.data.primary_currency.attributes.code
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name="Subscriptions",
            configuration_url=f"{URL(coordinator.config_entry.data[CONF_URL])}/subscriptions",
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_subscriptions")
            },
        )

    @property
    def native_value(self) -> StateType:
        """Return total expected amount of bills that have been paid this month."""
        now = datetime.now(tz=UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total = 0.0
        for bill in self.coordinator.data.bills.values():
            attrs = bill.attributes
            if not attrs.active:
                continue
            paid_dates = attrs.paid_dates
            if paid_dates and any(
                _parse_timestamp(pd.date) and _parse_timestamp(pd.date) >= month_start
                for pd in paid_dates
                if pd.date
            ):
                if attrs.amount_min is not None and attrs.amount_max is not None:
                    total += (float(attrs.amount_min) + float(attrs.amount_max)) / 2
                elif attrs.amount_min is not None:
                    total += float(attrs.amount_min)
                elif attrs.amount_max is not None:
                    total += float(attrs.amount_max)
        return total


def _parse_timestamp(value: str) -> datetime | None:
    """Parse a timestamp string from the API into a timezone-aware datetime."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
