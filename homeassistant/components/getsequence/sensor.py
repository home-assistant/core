"""Sensor platform for Sequence integration."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SequenceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def create_device_info(
    identifiers: set[tuple[str, str]],
    name: str,
    manufacturer: str = MANUFACTURER,
    model: str = MODEL,
    entry_id: str | None = None,
) -> DeviceInfo:
    """Create device info for sensors."""
    device_info = DeviceInfo(
        identifiers=identifiers,
        name=name,
        manufacturer=manufacturer,
        model=model,
    )
    if entry_id:
        device_info["via_device"] = (DOMAIN, entry_id)
    return device_info


def create_main_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Create device info for the main Sequence account."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
        name="Sequence Account",
        manufacturer=MANUFACTURER,
        model=MODEL,
        sw_version="1.0",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sequence sensor entities."""
    coordinator: SequenceDataUpdateCoordinator = config_entry.runtime_data

    entities: list[SensorEntity] = []

    # 1. AGGREGATE ACCOUNT SENSORS (Net balance and account type totals)

    # Net balance across all accounts
    entities.append(
        AggregateAccountSensor(
            coordinator,
            config_entry,
            "total_balance",
            ["pods", "income_sources"],
            "Net Balance",
            None,
            "Total balance across all accounts",
        )
    )

    # Account type totals
    total_configs = [
        ("pods", "pod_balance", "pods", "Pods"),
        ("liabilities", "liability_balance", "liabilities", "Liabilities"),
        ("investments", "investment_balance", "investments", "Investments"),
        ("income_sources", "income_source_balance", "income_sources", "Income Sources"),
        ("external", "uncategorized_external_balance", "external_accounts", "External"),
    ]

    entities.extend(
        AggregateAccountSensor(
            coordinator,
            config_entry,
            balance_key,
            [data_key],
            f"{display_name} Total",
            account_type,
            f"Total balance for {display_name.lower()} accounts",
        )
        for account_type, balance_key, data_key, display_name in total_configs
    )

    # 2. INDIVIDUAL ACCOUNT SENSORS (Balance sensors for each account)

    # Pod balance sensors (each gets its own device)
    entities.extend(
        AccountSensor(
            coordinator,
            config_entry,
            pod,
            "Pod",
            "pods",
            ["balance", "amountInDollars"],
        )
        for pod in coordinator.data.get("pods", [])
    )

    # Income source balance sensors
    entities.extend(
        AccountSensor(
            coordinator,
            config_entry,
            income_source,
            "Income Source",
            "income_sources",
            ["balance", "amountInDollars"],
        )
        for income_source in coordinator.data.get("income_sources", [])
    )

    # External account balance sensors
    entities.extend(
        AccountSensor(
            coordinator,
            config_entry,
            external,
            "External",
            "external_accounts",
            ["balance", "amountInDollars"],
        )
        for external in coordinator.data.get("external_accounts", [])
    )

    # 3. CASH FLOW SENSORS (Net, aggregate, and individual)

    # Net cash flow sensors (enabled by default for daily)
    cash_flow_periods = ["daily", "weekly", "monthly", "yearly"]
    entities.extend(
        [
            CashFlowSensor(
                coordinator,
                config_entry,
                period,
                "net",
                enabled_by_default=(period == "daily"),
            )
            for period in cash_flow_periods
        ]
    )

    # Aggregate cash flow sensors for each account type (disabled by default)
    aggregate_cash_flow_configs = [
        ("pod_balance", "Pods"),
        ("income_source_balance", "Income Sources"),
        ("uncategorized_external_balance", "External"),
    ]

    entities.extend(
        [
            CashFlowSensor(
                coordinator,
                config_entry,
                period,
                "aggregate",
                account_type=account_type,
                balance_source=balance_source,
                enabled_by_default=False,
            )
            for balance_source, account_type in aggregate_cash_flow_configs
            for period in cash_flow_periods
        ]
    )

    # Individual cash flow sensors for pods (disabled by default)
    entities.extend(
        [
            CashFlowSensor(
                coordinator,
                config_entry,
                period,
                "individual",
                account_data=pod,
                account_type="Pod",
                enabled_by_default=False,
            )
            for pod in coordinator.data.get("pods", [])
            for period in cash_flow_periods
        ]
    )

    # Individual cash flow sensors for income sources (disabled by default)
    entities.extend(
        [
            CashFlowSensor(
                coordinator,
                config_entry,
                period,
                "individual",
                account_data=income_source,
                account_type="Income Source",
                enabled_by_default=False,
            )
            for income_source in coordinator.data.get("income_sources", [])
            for period in cash_flow_periods
        ]
    )

    # Individual cash flow sensors for external accounts (disabled by default)
    entities.extend(
        [
            CashFlowSensor(
                coordinator,
                config_entry,
                period,
                "individual",
                account_data=external,
                account_type="External",
                enabled_by_default=False,
            )
            for external in coordinator.data.get("external_accounts", [])
            for period in cash_flow_periods
        ]
    )

    # 4. DATA AGE SENSOR (Last updated tracking)
    entities.append(DataAgeSensor(coordinator, config_entry))

    async_add_entities(entities)


class SequenceBaseSensor(
    CoordinatorEntity[SequenceDataUpdateCoordinator], SensorEntity
):
    """Base class for Sequence sensors."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = CURRENCY_DOLLAR
        self._attr_state_class = SensorStateClass.TOTAL


class AccountSensor(SequenceBaseSensor):
    """Unified sensor for individual account balances (pods and other account types)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        account_data: dict[str, Any],
        account_type: str,
        data_source_key: str,
        balance_path: list[str] | None = None,
    ) -> None:
        """Initialize the account sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            account_data: Account data dict with id, name
            account_type: Type like "Pod", "Income Source", "External Account", etc.
            data_source_key: Key in coordinator.data to find accounts (e.g., "pods", "incomeSources")
            balance_path: Path to balance value in account data (e.g., ["balance", "amountInDollars"])
        """
        super().__init__(coordinator, config_entry)
        self.account_data = account_data
        self.account_id = str(account_data["id"])
        self.account_name = account_data["name"]
        self.account_type = account_type
        self.data_source_key = data_source_key
        self.balance_path = balance_path or ["balance", "amountInDollars"]

        # Create unique identifier and device info
        type_key = account_type.lower().replace(" ", "_")
        self._attr_name = "Balance"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{type_key}_{self.account_id}_balance"
        )
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this account."""
        type_key = self.account_type.lower().replace(" ", "_")

        # Pods get their own standalone devices, others are under main device
        if self.account_type.lower() == "pod":
            return DeviceInfo(
                identifiers={(DOMAIN, f"pod_{self.account_id}")},
                name=self.account_name,
                manufacturer=MANUFACTURER,
                model="Pod Account",
                sw_version="1.0",
                via_device=(
                    DOMAIN,
                    self.config_entry.unique_id or self.config_entry.entry_id,
                ),
            )

        return DeviceInfo(
            identifiers={(DOMAIN, f"{type_key}_{self.account_id}")},
            name=f"{self.account_name} ({self.account_type})",
            manufacturer=MANUFACTURER,
            model=f"{self.account_type} Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return the balance of the account."""
        # Find current account data in coordinator
        accounts = self.coordinator.data.get(self.data_source_key, [])
        for account in accounts:
            if str(account["id"]) == self.account_id:
                # Navigate to balance value using path
                current = account
                for key in self.balance_path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return None

                # For pods, check for errors in balance
                if self.account_type.lower() == "pod" and "balance" in account:
                    balance_info = account["balance"]
                    if balance_info.get("error") is not None:
                        _LOGGER.warning(
                            "Error getting balance for %s %s: %s",
                            self.account_type.lower(),
                            self.account_name,
                            balance_info.get("error"),
                        )
                        return None

                return current if isinstance(current, (int, float)) else None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        # Find current account data in coordinator
        accounts = self.coordinator.data.get(self.data_source_key, [])
        for account in accounts:
            if str(account["id"]) == self.account_id:
                attrs = {
                    "account_id": self.account_id,
                    "account_name": self.account_name,
                    "account_type": self.account_type,
                }

                # Add pod-specific or account-specific attributes
                if self.account_type.lower() == "pod" and "balance" in account:
                    balance_info = account["balance"]
                    attrs["balance_error"] = balance_info.get("error")

                # Add raw balance data if available
                if "balance" in account:
                    attrs["raw_balance_data"] = account["balance"]

                return attrs
        return {}

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if this account still exists in the data
        accounts = self.coordinator.data.get(self.data_source_key, [])
        return any(str(account["id"]) == self.account_id for account in accounts)


class AggregateAccountSensor(SequenceBaseSensor):
    """Unified sensor for aggregate balances across account types."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        balance_key: str,
        data_sources: list[str] | None = None,
        display_name: str = "Total",
        account_type: str | None = None,
        description: str | None = None,
    ) -> None:
        """Initialize the aggregate account sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            balance_key: Key in coordinator.data for the balance value
            data_sources: List of data source keys for extra attributes (e.g., ["pods", "incomeSources"])
            display_name: Display name for the sensor (e.g., "Pod Total", "Net Balance")
            account_type: Account type for unique ID (e.g., "pod", "income_source", None for net)
            description: Additional description for attributes
        """
        super().__init__(coordinator, config_entry)
        self.balance_key = balance_key
        self.data_sources = data_sources or []
        self.display_name = display_name
        self.account_type = account_type
        self.description = description

        # Create unique identifier based on account type or "net" for net balance
        type_key = account_type.lower() if account_type else "net"
        self._attr_name = (
            f"{display_name} Balance"
            if "balance" not in display_name.lower()
            else display_name
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{type_key}_total"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main account."""
        return create_main_device_info(self.config_entry)

    @property
    def native_value(self) -> float | None:
        """Return the aggregate balance."""
        return self.coordinator.data.get(self.balance_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}

        # Add account counts for each data source
        for data_source in self.data_sources:
            accounts = self.coordinator.data.get(data_source, [])
            source_name = data_source.rstrip("s")  # Remove trailing 's' for singular
            attrs[f"{source_name}_count"] = len(accounts)

        # Add account type if specified
        if self.account_type:
            attrs["account_type"] = self.account_type

        # Add description if specified
        if self.description:
            attrs["description"] = self.description

        # Add balance key for debugging
        attrs["balance_source"] = self.balance_key

        return attrs


class CashFlowSensor(SequenceBaseSensor):
    """Unified sensor for cash flow tracking across different scopes and periods."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        period: str,
        scope: str = "aggregate",  # "aggregate", "individual", "net"
        account_data: dict[str, Any] | None = None,
        account_type: str | None = None,
        balance_source: str | None = None,
        enabled_by_default: bool = False,
    ) -> None:
        """Initialize the cash flow sensor.

        Args:
            coordinator: Data coordinator
            config_entry: Config entry
            period: Period for cash flow tracking (daily, weekly, monthly, yearly)
            scope: Scope of tracking ("aggregate", "individual", "net")
            account_data: Account data for individual scope (pod data, etc.)
            account_type: Account type for aggregate scope ("Pod", "Income Source", etc.)
            balance_source: Source key for balance data in coordinator
            enabled_by_default: Whether sensor is enabled by default
        """
        super().__init__(coordinator, config_entry)
        self._period = period
        self._scope = scope
        self.account_data = account_data
        self.account_type = account_type
        self._balance_source = balance_source
        self._previous_balance: float | None = None
        self._flow_total: float = 0.0

        # Set up names and IDs based on scope
        if scope == "individual" and account_data:
            self.account_id = str(account_data["id"])
            self.account_name = account_data["name"]
            self._attr_name = f"Cash Flow {period.title()}"
            self._attr_unique_id = f"{config_entry.entry_id}_{self._get_scope_key()}_{self.account_id}_cash_flow_{period}"
        elif scope == "aggregate" and account_type:
            type_key = account_type.lower().replace(" ", "_")
            self._attr_name = f"{account_type} Cash Flow {period.title()}"
            self._attr_unique_id = (
                f"{config_entry.entry_id}_{type_key}_cash_flow_{period}"
            )
        else:  # net scope
            self._attr_name = f"Cash Flow {period.title()}"
            self._attr_unique_id = f"{config_entry.entry_id}_cash_flow_{period}"

        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_entity_registry_enabled_default = enabled_by_default

    def _get_scope_key(self) -> str:
        """Get scope key for unique ID."""
        if self._scope == "individual" and self.account_type:
            return self.account_type.lower().replace(" ", "_")
        return self._scope

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information based on scope."""
        if self._scope == "individual" and self.account_data:
            # Individual accounts get their own devices
            account_id = str(self.account_data["id"])
            account_name = self.account_data["name"]
            if self.account_type and self.account_type.lower() == "pod":
                return DeviceInfo(
                    identifiers={(DOMAIN, f"pod_{account_id}")},
                    name=account_name,
                    manufacturer=MANUFACTURER,
                    model="Pod Account",
                    sw_version="1.0",
                    via_device=(
                        DOMAIN,
                        self.config_entry.unique_id or self.config_entry.entry_id,
                    ),
                )
            # Other individual account types
            type_key = (
                self.account_type.lower().replace(" ", "_")
                if self.account_type
                else "account"
            )
            return DeviceInfo(
                identifiers={(DOMAIN, f"{type_key}_{account_id}")},
                name=f"{account_name} ({self.account_type})"
                if self.account_type
                else account_name,
                manufacturer=MANUFACTURER,
                model=f"{self.account_type} Account"
                if self.account_type
                else "Account",
                sw_version="1.0",
                via_device=(
                    DOMAIN,
                    self.config_entry.unique_id or self.config_entry.entry_id,
                ),
            )

        # For aggregate and net scope, use main device
        return create_main_device_info(self.config_entry)

    @property
    def native_value(self) -> float | None:
        """Return the cash flow for this period."""
        current_balance = self._get_current_balance()
        if current_balance is None:
            return None

        # Calculate flow based on balance change
        if self._previous_balance is not None:
            flow_change = current_balance - self._previous_balance
            self._flow_total += flow_change

        self._previous_balance = current_balance
        return self._flow_total

    def _get_current_balance(self) -> float | None:
        """Get current balance based on scope."""
        if self._scope == "individual" and self.account_data:
            # Find current account data in coordinator
            data_source = self._get_data_source()
            accounts = self.coordinator.data.get(data_source, [])
            for account in accounts:
                if str(account["id"]) == self.account_id:
                    if self.account_type and self.account_type.lower() == "pod":
                        balance_info = account.get("balance", {})
                        if balance_info.get("error") is None:
                            return balance_info.get("amountInDollars")
                    else:
                        return account.get("balance")
            return None

        if self._scope == "aggregate" and self._balance_source:
            # Use specified balance source for aggregate
            return self.coordinator.data.get(self._balance_source)

        # Net scope uses total balance
        return self.coordinator.data.get("total_balance")

    def _get_data_source(self) -> str:
        """Get data source key based on account type."""
        if self.account_type and self.account_type.lower() == "pod":
            return "pods"
        if self.account_type and "income" in self.account_type.lower():
            return "income_sources"
        if self.account_type and "liability" in self.account_type.lower():
            return "liabilities"
        if self.account_type and "external" in self.account_type.lower():
            return "externalAccounts"
        return "accounts"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "period": self._period,
            "scope": self._scope,
            "previous_balance": self._previous_balance,
        }

        if self._scope == "individual" and self.account_data:
            attrs.update(
                {
                    "account_id": self.account_id,
                    "account_name": self.account_name,
                    "account_type": self.account_type,
                }
            )
        elif self._scope == "aggregate" and self.account_type:
            attrs.update(
                {
                    "account_type": self.account_type,
                    "balance_source": self._balance_source,
                }
            )

        return attrs


class DataAgeSensor(SequenceBaseSensor):
    """Sensor showing how old the current data is."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the data age sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Data Age"
        self._attr_unique_id = f"{config_entry.entry_id}_data_age"
        self._attr_has_entity_name = True
        self._attr_device_class = None  # No device class for time duration
        self._attr_native_unit_of_measurement = "minutes"
        self._attr_state_class = None  # No state class for age

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main account."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.config_entry.unique_id or self.config_entry.entry_id)
            },
            name="Sequence Account",
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version="1.0",
        )

    @property
    def native_value(self) -> float | None:
        """Return the age of the data in minutes."""
        if self.coordinator.last_update_success_time:
            age = datetime.now(UTC) - self.coordinator.last_update_success_time
            return round(age.total_seconds() / 60, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "last_update": self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time
            else None,
            "update_interval_minutes": self.coordinator.update_interval.total_seconds()
            / 60
            if self.coordinator.update_interval
            else None,
            "last_update_success": self.coordinator.last_update_success,
        }
