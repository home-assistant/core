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

from .const import (
    ACCOUNT_TYPE_INCOME_SOURCE,
    ACCOUNT_TYPE_INVESTMENT,
    ACCOUNT_TYPE_LIABILITY,
    ACCOUNT_TYPE_POD,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .coordinator import SequenceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sequence sensor entities."""
    coordinator: SequenceDataUpdateCoordinator = config_entry.runtime_data

    entities: list[SensorEntity] = []

    # First add account-level aggregate sensors (creates main account device)
    entities.extend(
        [
            NetBalanceSensor(coordinator, config_entry),
            PodTotalSensor(coordinator, config_entry),
            LiabilityTotalSensor(coordinator, config_entry),
            InvestmentTotalSensor(coordinator, config_entry),
            IncomeSourceTotalSensor(coordinator, config_entry),
            ExternalTotalSensor(coordinator, config_entry),
            DataAgeSensor(coordinator, config_entry),
            CashFlowDailySensor(coordinator, config_entry),
            CashFlowWeeklySensor(coordinator, config_entry),
            CashFlowMonthlySensor(coordinator, config_entry),
            CashFlowYearlySensor(coordinator, config_entry),
        ]
    )

    # Add individual pod balance sensors (each pod as a separate device)
    entities.extend(
        [
            PodBalanceSensor(coordinator, config_entry, pod)
            for pod in coordinator.data.get("pods", [])
        ]
    )

    # Add per-pod cash flow sensors
    entities.extend(
        [
            PodCashFlowDailySensor(coordinator, config_entry, pod)
            for pod in coordinator.data.get("pods", [])
        ]
    )

    # Add individual income source utility meters (disabled by default)
    for income_source in coordinator.data.get("income_sources", []):
        entities.extend(
            [
                IncomeSourceIndividualCashFlowDailySensor(
                    coordinator, config_entry, income_source
                ),
                IncomeSourceIndividualCashFlowWeeklySensor(
                    coordinator, config_entry, income_source
                ),
                IncomeSourceIndividualCashFlowMonthlySensor(
                    coordinator, config_entry, income_source
                ),
                IncomeSourceIndividualCashFlowYearlySensor(
                    coordinator, config_entry, income_source
                ),
            ]
        )

    # Add individual external account utility meters (disabled by default)
    for external in coordinator.data.get("external_accounts", []):
        entities.extend(
            [
                ExternalIndividualCashFlowDailySensor(
                    coordinator, config_entry, external
                ),
                ExternalIndividualCashFlowWeeklySensor(
                    coordinator, config_entry, external
                ),
                ExternalIndividualCashFlowMonthlySensor(
                    coordinator, config_entry, external
                ),
                ExternalIndividualCashFlowYearlySensor(
                    coordinator, config_entry, external
                ),
            ]
        )

    # Add individual sensors for other account types as separate devices
    entities.extend(
        [
            AccountBalanceSensor(
                coordinator, config_entry, income_source, ACCOUNT_TYPE_INCOME_SOURCE
            )
            for income_source in coordinator.data.get("income_sources", [])
        ]
    )

    # Add external account sensors (including configured liabilities/investments)
    entities.extend(
        [
            AccountBalanceSensor(coordinator, config_entry, external, "External")
            for external in coordinator.data.get("external_accounts", [])
        ]
    )

    # Add utility meters for Income Sources (disabled by default)
    entities.extend(
        [
            IncomeSourceCashFlowDailySensor(coordinator, config_entry),
            IncomeSourceCashFlowWeeklySensor(coordinator, config_entry),
            IncomeSourceCashFlowMonthlySensor(coordinator, config_entry),
            IncomeSourceCashFlowYearlySensor(coordinator, config_entry),
        ]
    )

    # Add utility meters for Pods (disabled by default)
    entities.extend(
        [
            PodsCashFlowDailySensor(coordinator, config_entry),
            PodsCashFlowWeeklySensor(coordinator, config_entry),
            PodsCashFlowMonthlySensor(coordinator, config_entry),
            PodsCashFlowYearlySensor(coordinator, config_entry),
        ]
    )

    # Add utility meters for External accounts (disabled by default)
    entities.extend(
        [
            ExternalCashFlowDailySensor(coordinator, config_entry),
            ExternalCashFlowWeeklySensor(coordinator, config_entry),
            ExternalCashFlowMonthlySensor(coordinator, config_entry),
            ExternalCashFlowYearlySensor(coordinator, config_entry),
        ]
    )

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


class PodBalanceSensor(SequenceBaseSensor):
    """Sensor for individual pod balance (creates its own device)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pod_data: dict[str, Any],
    ) -> None:
        """Initialize the pod sensor."""
        super().__init__(coordinator, config_entry)
        self.pod_data = pod_data
        self.pod_id = str(pod_data["id"])
        self.pod_name = pod_data["name"]

        # Remove "Sequence" prefix from entity name
        self._attr_name = "Balance"
        self._attr_unique_id = f"{config_entry.entry_id}_pod_{self.pod_id}_balance"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this pod."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"pod_{self.pod_id}")},
            name=self.pod_name,
            manufacturer=MANUFACTURER,
            model="Pod Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return the balance of the pod."""
        # Find current pod data in coordinator
        for pod in self.coordinator.data.get("pods", []):
            if str(pod["id"]) == self.pod_id:
                balance_info = pod.get("balance", {})
                if balance_info.get("error") is None:
                    return balance_info.get("amountInDollars")
                _LOGGER.warning(
                    "Error getting balance for pod %s: %s",
                    self.pod_name,
                    balance_info.get("error"),
                )
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        # Find current pod data in coordinator
        for pod in self.coordinator.data.get("pods", []):
            if str(pod["id"]) == self.pod_id:
                balance_info = pod.get("balance", {})
                return {
                    "pod_id": self.pod_id,
                    "pod_name": self.pod_name,
                    "account_type": ACCOUNT_TYPE_POD,
                    "balance_error": balance_info.get("error"),
                }
        return {}

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if this pod still exists in the data
        for pod in self.coordinator.data.get("pods", []):
            if str(pod["id"]) == self.pod_id:
                return True
        return False


class NetBalanceSensor(SequenceBaseSensor):
    """Sensor for net balance across all accounts (under main account device)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the net balance sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Net Balance"
        self._attr_unique_id = f"{config_entry.entry_id}_net_balance"
        self._attr_has_entity_name = True

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
        """Return the total balance across all accounts."""
        return self.coordinator.data.get("total_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        pods = self.coordinator.data.get("pods", [])
        income_sources = self.coordinator.data.get("income_sources", [])

        return {
            "pod_count": len(pods),
            "income_source_count": len(income_sources),
            "pod_balance": self.coordinator.data.get("pod_balance"),
            "account_breakdown": {
                pod["name"]: pod.get("balance", {}).get("amountInDollars")
                for pod in pods
                if pod.get("balance", {}).get("error") is None
            },
        }


class PodTotalSensor(SequenceBaseSensor):
    """Sensor for total balance across all pods only (under main account device)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pod total sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pods Total"
        self._attr_unique_id = f"{config_entry.entry_id}_pods_total"
        self._attr_has_entity_name = True

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
        """Return the total balance across all pods."""
        return self.coordinator.data.get("pod_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        pods = self.coordinator.data.get("pods", [])

        return {
            "pod_count": len(pods),
            "pod_breakdown": {
                pod["name"]: pod.get("balance", {}).get("amountInDollars")
                for pod in pods
                if pod.get("balance", {}).get("error") is None
            },
        }


class CashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow (utility meter style)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Cash Flow Daily"
        self._attr_unique_id = f"{config_entry.entry_id}_cash_flow_daily"
        self._attr_has_entity_name = True
        # For cash flow tracking, don't use device class monetary
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        # Only net cash flow is enabled by default
        self._attr_entity_registry_enabled_default = True

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
        """Return daily cumulative positive cash flow."""
        current_balance = self.coordinator.data.get("total_balance")

        if current_balance is None:
            return None

        # For cash flow tracking, we only track positive increases
        # This emulates a utility meter for financial inflows
        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:  # Only track positive cash flow
                self._daily_flow += change

        self._previous_balance = current_balance
        return self._daily_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "daily",
            "source": "net_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class CashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow (utility meter style)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Cash Flow Weekly"
        self._attr_unique_id = f"{config_entry.entry_id}_cash_flow_weekly"
        self._attr_has_entity_name = True
        # For cash flow tracking, don't use device class monetary
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        # Disabled by default
        self._attr_entity_registry_enabled_default = False

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
        """Return weekly cumulative positive cash flow."""
        current_balance = self.coordinator.data.get("total_balance")

        if current_balance is None:
            return None

        # For cash flow tracking, we only track positive increases
        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:  # Only track positive cash flow
                self._weekly_flow += change

        self._previous_balance = current_balance
        return self._weekly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "weekly",
            "source": "net_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class CashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow (utility meter style)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Cash Flow Monthly"
        self._attr_unique_id = f"{config_entry.entry_id}_cash_flow_monthly"
        self._attr_has_entity_name = True
        # For cash flow tracking, don't use device class monetary
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        # Disabled by default
        self._attr_entity_registry_enabled_default = False

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
        """Return monthly cumulative positive cash flow."""
        current_balance = self.coordinator.data.get("total_balance")

        if current_balance is None:
            return None

        # For cash flow tracking, we only track positive increases
        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:  # Only track positive cash flow
                self._monthly_flow += change

        self._previous_balance = current_balance
        return self._monthly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "monthly",
            "source": "net_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class CashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow (utility meter style)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Cash Flow Yearly"
        self._attr_unique_id = f"{config_entry.entry_id}_cash_flow_yearly"
        self._attr_has_entity_name = True
        # For cash flow tracking, don't use device class monetary
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        # Disabled by default
        self._attr_entity_registry_enabled_default = False

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
        """Return yearly cumulative positive cash flow."""
        current_balance = self.coordinator.data.get("total_balance")

        if current_balance is None:
            return None

        # For cash flow tracking, we only track positive increases
        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:  # Only track positive cash flow
                self._yearly_flow += change

        self._previous_balance = current_balance
        return self._yearly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "yearly",
            "source": "net_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class LiabilityTotalSensor(SequenceBaseSensor):
    """Sensor for total balance across all liability accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the liability total sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Liabilities Total"
        self._attr_unique_id = f"{config_entry.entry_id}_liabilities_total"
        self._attr_has_entity_name = True

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
        """Return the total balance across all liability accounts."""
        return self.coordinator.data.get("liability_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        liabilities = self.coordinator.data.get("liabilities", [])

        return {
            "liability_count": len(liabilities),
            "liability_breakdown": {
                liability["name"]: liability.get("balance", {}).get("amountInDollars")
                for liability in liabilities
                if liability.get("balance", {}).get("error") is None
            },
        }


class InvestmentTotalSensor(SequenceBaseSensor):
    """Sensor for total balance across all investment accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the investment total sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Investments Total"
        self._attr_unique_id = f"{config_entry.entry_id}_investments_total"
        self._attr_has_entity_name = True

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
        """Return the total balance across all investment accounts."""
        return self.coordinator.data.get("investment_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        investments = self.coordinator.data.get("investments", [])

        return {
            "investment_count": len(investments),
            "investment_breakdown": {
                investment["name"]: investment.get("balance", {}).get("amountInDollars")
                for investment in investments
                if investment.get("balance", {}).get("error") is None
            },
        }


class IncomeSourceTotalSensor(SequenceBaseSensor):
    """Sensor for total balance across all income source accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the income source total sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Income Sources Total"
        self._attr_unique_id = f"{config_entry.entry_id}_income_sources_total"
        self._attr_has_entity_name = True

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
        """Return the total balance across all income source accounts."""
        return self.coordinator.data.get("income_source_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        income_sources = self.coordinator.data.get("income_sources", [])

        return {
            "income_source_count": len(income_sources),
            "income_source_breakdown": {
                source["name"]: source.get("balance", {}).get("amountInDollars")
                for source in income_sources
                if source.get("balance", {}).get("error") is None
            },
        }


class ExternalTotalSensor(SequenceBaseSensor):
    """Sensor for total balance across uncategorized external accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the external total sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "External Total"
        self._attr_unique_id = f"{config_entry.entry_id}_external_total"
        self._attr_has_entity_name = True

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
        """Return the total balance across uncategorized external accounts."""
        return self.coordinator.data.get("uncategorized_external_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        uncategorized_external = self.coordinator.data.get(
            "uncategorized_external_accounts", []
        )

        return {
            "external_count": len(uncategorized_external),
            "external_breakdown": {
                account["name"]: account.get("balance", {}).get("amountInDollars")
                for account in uncategorized_external
                if account.get("balance", {}).get("error") is None
            },
        }


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


class PodCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for individual pods."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pod_data: dict[str, Any],
    ) -> None:
        """Initialize the pod cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self.pod_data = pod_data
        self.pod_id = str(pod_data["id"])
        self.pod_name = pod_data["name"]

        self._attr_name = "Cash Flow Daily"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_pod_{self.pod_id}_cash_flow_daily"
        )
        self._attr_has_entity_name = True
        # For cash flow tracking, don't use device class monetary
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        # Disabled by default
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this pod."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"pod_{self.pod_id}")},
            name=self.pod_name,
            manufacturer=MANUFACTURER,
            model="Pod Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return daily cumulative positive cash flow for this pod."""
        # Find current pod data in coordinator
        for pod in self.coordinator.data.get("pods", []):
            if str(pod["id"]) == self.pod_id:
                balance_info = pod.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                # For cash flow tracking, we only track positive increases
                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:  # Only track positive cash flow
                        self._daily_flow += change

                self._previous_balance = current_balance
                return self._daily_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "pod_id": self.pod_id,
            "pod_name": self.pod_name,
            "period": "daily",
            "source": "pod_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if this pod still exists in the data
        for pod in self.coordinator.data.get("pods", []):
            if str(pod["id"]) == self.pod_id:
                return True
        return False


class AccountBalanceSensor(SequenceBaseSensor):
    """Sensor for individual account balance (non-pod accounts)."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        account_data: dict[str, Any],
        account_type: str,
    ) -> None:
        """Initialize the account sensor."""
        super().__init__(coordinator, config_entry)
        self.account_data = account_data
        self.account_id = str(account_data["id"])
        self.account_name = account_data["name"]
        self.account_type = account_type

        # Remove "Sequence" prefix from entity name
        self._attr_name = "Balance"
        self._attr_unique_id = f"{config_entry.entry_id}_{account_type.lower().replace(' ', '_')}_{self.account_id}_balance"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this account."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.account_type.lower().replace(' ', '_')}_{self.account_id}",
                )
            },
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
        # Find current account data in coordinator based on type
        account_list_key = {
            ACCOUNT_TYPE_LIABILITY: "liabilities",
            ACCOUNT_TYPE_INVESTMENT: "investments",
            ACCOUNT_TYPE_INCOME_SOURCE: "income_sources",
            "External": "external_accounts",
        }.get(self.account_type, "external_accounts")

        for account in self.coordinator.data.get(account_list_key, []):
            if str(account["id"]) == self.account_id:
                balance_info = account.get("balance", {})
                if balance_info.get("error") is None:
                    return balance_info.get("amountInDollars")
                _LOGGER.warning(
                    "Error getting balance for %s %s: %s",
                    self.account_type,
                    self.account_name,
                    balance_info.get("error"),
                )
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        # Find current account data in coordinator
        account_list_key = {
            ACCOUNT_TYPE_LIABILITY: "liabilities",
            ACCOUNT_TYPE_INVESTMENT: "investments",
            ACCOUNT_TYPE_INCOME_SOURCE: "income_sources",
            "External": "external_accounts",
        }.get(self.account_type, "external_accounts")

        for account in self.coordinator.data.get(account_list_key, []):
            if str(account["id"]) == self.account_id:
                balance_info = account.get("balance", {})
                return {
                    "account_id": self.account_id,
                    "account_name": self.account_name,
                    "account_type": self.account_type,
                    "balance_error": balance_info.get("error"),
                }
        return {}

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if this account still exists in the data
        account_list_key = {
            ACCOUNT_TYPE_LIABILITY: "liabilities",
            ACCOUNT_TYPE_INVESTMENT: "investments",
            ACCOUNT_TYPE_INCOME_SOURCE: "income_sources",
            "External": "external_accounts",
        }.get(self.account_type, "external_accounts")

        for account in self.coordinator.data.get(account_list_key, []):
            if str(account["id"]) == self.account_id:
                return True
        return False


class IncomeSourceCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the income source cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Income Sources Cash Flow Daily"
        self._attr_unique_id = f"{config_entry.entry_id}_income_sources_cash_flow_daily"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return daily cumulative positive cash flow for income sources."""
        current_balance = self.coordinator.data.get("income_source_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._daily_flow += change

        self._previous_balance = current_balance
        return self._daily_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "daily",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceCashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow for income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the income source cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Income Sources Cash Flow Weekly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_sources_cash_flow_weekly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return weekly cumulative positive cash flow for income sources."""
        current_balance = self.coordinator.data.get("income_source_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._weekly_flow += change

        self._previous_balance = current_balance
        return self._weekly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "weekly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceCashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow for income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the income source cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Income Sources Cash Flow Monthly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_sources_cash_flow_monthly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return monthly cumulative positive cash flow for income sources."""
        current_balance = self.coordinator.data.get("income_source_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._monthly_flow += change

        self._previous_balance = current_balance
        return self._monthly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "monthly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceCashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow for income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the income source cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Income Sources Cash Flow Yearly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_sources_cash_flow_yearly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return yearly cumulative positive cash flow for income sources."""
        current_balance = self.coordinator.data.get("income_source_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._yearly_flow += change

        self._previous_balance = current_balance
        return self._yearly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "yearly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class PodsCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for all pods combined."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pods cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pods Cash Flow Daily"
        self._attr_unique_id = f"{config_entry.entry_id}_pods_cash_flow_daily"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return daily cumulative positive cash flow for all pods."""
        current_balance = self.coordinator.data.get("pod_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._daily_flow += change

        self._previous_balance = current_balance
        return self._daily_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "daily",
            "source": "pod_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class PodsCashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow for all pods combined."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pods cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pods Cash Flow Weekly"
        self._attr_unique_id = f"{config_entry.entry_id}_pods_cash_flow_weekly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return weekly cumulative positive cash flow for all pods."""
        current_balance = self.coordinator.data.get("pod_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._weekly_flow += change

        self._previous_balance = current_balance
        return self._weekly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "weekly",
            "source": "pod_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class PodsCashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow for all pods combined."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pods cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pods Cash Flow Monthly"
        self._attr_unique_id = f"{config_entry.entry_id}_pods_cash_flow_monthly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return monthly cumulative positive cash flow for all pods."""
        current_balance = self.coordinator.data.get("pod_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._monthly_flow += change

        self._previous_balance = current_balance
        return self._monthly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "monthly",
            "source": "pod_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class PodsCashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow for all pods combined."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the pods cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Pods Cash Flow Yearly"
        self._attr_unique_id = f"{config_entry.entry_id}_pods_cash_flow_yearly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return yearly cumulative positive cash flow for all pods."""
        current_balance = self.coordinator.data.get("pod_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._yearly_flow += change

        self._previous_balance = current_balance
        return self._yearly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "yearly",
            "source": "pod_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


# Individual Income Source Utility Meters (disabled by default)
class IncomeSourceIndividualCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for individual income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        income_source_data: dict[str, Any],
    ) -> None:
        """Initialize the income source cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self.income_source_data = income_source_data
        self.account_id = str(income_source_data["id"])
        self.account_name = income_source_data["name"]

        self._attr_name = "Cash Flow Daily"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_source_{self.account_id}_cash_flow_daily"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this income source."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"income_source_{self.account_id}")},
            name=f"{self.account_name} (Income Source)",
            manufacturer=MANUFACTURER,
            model="Income Source Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return daily cumulative positive cash flow for this income source."""
        for income_source in self.coordinator.data.get("income_sources", []):
            if str(income_source["id"]) == self.account_id:
                balance_info = income_source.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._daily_flow += change

                self._previous_balance = current_balance
                return self._daily_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "Income Source",
            "period": "daily",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceIndividualCashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow for individual income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        income_source_data: dict[str, Any],
    ) -> None:
        """Initialize the income source cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self.income_source_data = income_source_data
        self.account_id = str(income_source_data["id"])
        self.account_name = income_source_data["name"]

        self._attr_name = "Cash Flow Weekly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_source_{self.account_id}_cash_flow_weekly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this income source."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"income_source_{self.account_id}")},
            name=f"{self.account_name} (Income Source)",
            manufacturer=MANUFACTURER,
            model="Income Source Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return weekly cumulative positive cash flow for this income source."""
        for income_source in self.coordinator.data.get("income_sources", []):
            if str(income_source["id"]) == self.account_id:
                balance_info = income_source.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._weekly_flow += change

                self._previous_balance = current_balance
                return self._weekly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "Income Source",
            "period": "weekly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceIndividualCashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow for individual income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        income_source_data: dict[str, Any],
    ) -> None:
        """Initialize the income source cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self.income_source_data = income_source_data
        self.account_id = str(income_source_data["id"])
        self.account_name = income_source_data["name"]

        self._attr_name = "Cash Flow Monthly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_source_{self.account_id}_cash_flow_monthly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this income source."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"income_source_{self.account_id}")},
            name=f"{self.account_name} (Income Source)",
            manufacturer=MANUFACTURER,
            model="Income Source Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return monthly cumulative positive cash flow for this income source."""
        for income_source in self.coordinator.data.get("income_sources", []):
            if str(income_source["id"]) == self.account_id:
                balance_info = income_source.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._monthly_flow += change

                self._previous_balance = current_balance
                return self._monthly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "Income Source",
            "period": "monthly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class IncomeSourceIndividualCashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow for individual income sources."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        income_source_data: dict[str, Any],
    ) -> None:
        """Initialize the income source cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self.income_source_data = income_source_data
        self.account_id = str(income_source_data["id"])
        self.account_name = income_source_data["name"]

        self._attr_name = "Cash Flow Yearly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_income_source_{self.account_id}_cash_flow_yearly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this income source."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"income_source_{self.account_id}")},
            name=f"{self.account_name} (Income Source)",
            manufacturer=MANUFACTURER,
            model="Income Source Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return yearly cumulative positive cash flow for this income source."""
        for income_source in self.coordinator.data.get("income_sources", []):
            if str(income_source["id"]) == self.account_id:
                balance_info = income_source.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._yearly_flow += change

                self._previous_balance = current_balance
                return self._yearly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "Income Source",
            "period": "yearly",
            "source": "income_source_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


# Individual External Account Utility Meters (disabled by default)
class ExternalIndividualCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for individual external accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        external_data: dict[str, Any],
    ) -> None:
        """Initialize the external cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self.external_data = external_data
        self.account_id = str(external_data["id"])
        self.account_name = external_data["name"]

        self._attr_name = "Cash Flow Daily"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_external_{self.account_id}_cash_flow_daily"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this external account."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"external_{self.account_id}")},
            name=f"{self.account_name} (External)",
            manufacturer=MANUFACTURER,
            model="External Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return daily cumulative positive cash flow for this external account."""
        for external in self.coordinator.data.get("external_accounts", []):
            if str(external["id"]) == self.account_id:
                balance_info = external.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._daily_flow += change

                self._previous_balance = current_balance
                return self._daily_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "External",
            "period": "daily",
            "source": "external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalIndividualCashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow for individual external accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        external_data: dict[str, Any],
    ) -> None:
        """Initialize the external cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self.external_data = external_data
        self.account_id = str(external_data["id"])
        self.account_name = external_data["name"]

        self._attr_name = "Cash Flow Weekly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_external_{self.account_id}_cash_flow_weekly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this external account."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"external_{self.account_id}")},
            name=f"{self.account_name} (External)",
            manufacturer=MANUFACTURER,
            model="External Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return weekly cumulative positive cash flow for this external account."""
        for external in self.coordinator.data.get("external_accounts", []):
            if str(external["id"]) == self.account_id:
                balance_info = external.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._weekly_flow += change

                self._previous_balance = current_balance
                return self._weekly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "External",
            "period": "weekly",
            "source": "external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalIndividualCashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow for individual external accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        external_data: dict[str, Any],
    ) -> None:
        """Initialize the external cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self.external_data = external_data
        self.account_id = str(external_data["id"])
        self.account_name = external_data["name"]

        self._attr_name = "Cash Flow Monthly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_external_{self.account_id}_cash_flow_monthly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this external account."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"external_{self.account_id}")},
            name=f"{self.account_name} (External)",
            manufacturer=MANUFACTURER,
            model="External Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return monthly cumulative positive cash flow for this external account."""
        for external in self.coordinator.data.get("external_accounts", []):
            if str(external["id"]) == self.account_id:
                balance_info = external.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._monthly_flow += change

                self._previous_balance = current_balance
                return self._monthly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "External",
            "period": "monthly",
            "source": "external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalIndividualCashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow for individual external accounts."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
        external_data: dict[str, Any],
    ) -> None:
        """Initialize the external cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self.external_data = external_data
        self.account_id = str(external_data["id"])
        self.account_name = external_data["name"]

        self._attr_name = "Cash Flow Yearly"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_external_{self.account_id}_cash_flow_yearly"
        )
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this external account."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"external_{self.account_id}")},
            name=f"{self.account_name} (External)",
            manufacturer=MANUFACTURER,
            model="External Account",
            sw_version="1.0",
            via_device=(
                DOMAIN,
                self.config_entry.unique_id or self.config_entry.entry_id,
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return yearly cumulative positive cash flow for this external account."""
        for external in self.coordinator.data.get("external_accounts", []):
            if str(external["id"]) == self.account_id:
                balance_info = external.get("balance", {})
                if balance_info.get("error") is not None:
                    return None

                current_balance = balance_info.get("amountInDollars")
                if current_balance is None:
                    return None

                if self._previous_balance is not None:
                    change = current_balance - self._previous_balance
                    if change > 0:
                        self._yearly_flow += change

                self._previous_balance = current_balance
                return self._yearly_flow

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": "External",
            "period": "yearly",
            "source": "external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


# Aggregate External Cash Flow Sensors (disabled by default)
class ExternalCashFlowDailySensor(SequenceBaseSensor):
    """Sensor for tracking daily cash flow for external total."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the external cash flow daily sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "External Cash Flow Daily"
        self._attr_unique_id = f"{config_entry.entry_id}_external_cash_flow_daily"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._daily_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return daily cumulative positive cash flow for external total."""
        current_balance = self.coordinator.data.get("uncategorized_external_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._daily_flow += change

        self._previous_balance = current_balance
        return self._daily_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "daily",
            "source": "uncategorized_external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalCashFlowWeeklySensor(SequenceBaseSensor):
    """Sensor for tracking weekly cash flow for external total."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the external cash flow weekly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "External Cash Flow Weekly"
        self._attr_unique_id = f"{config_entry.entry_id}_external_cash_flow_weekly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._weekly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return weekly cumulative positive cash flow for external total."""
        current_balance = self.coordinator.data.get("uncategorized_external_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._weekly_flow += change

        self._previous_balance = current_balance
        return self._weekly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "weekly",
            "source": "uncategorized_external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalCashFlowMonthlySensor(SequenceBaseSensor):
    """Sensor for tracking monthly cash flow for external total."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the external cash flow monthly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "External Cash Flow Monthly"
        self._attr_unique_id = f"{config_entry.entry_id}_external_cash_flow_monthly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._monthly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return monthly cumulative positive cash flow for external total."""
        current_balance = self.coordinator.data.get("uncategorized_external_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._monthly_flow += change

        self._previous_balance = current_balance
        return self._monthly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "monthly",
            "source": "uncategorized_external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }


class ExternalCashFlowYearlySensor(SequenceBaseSensor):
    """Sensor for tracking yearly cash flow for external total."""

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the external cash flow yearly sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "External Cash Flow Yearly"
        self._attr_unique_id = f"{config_entry.entry_id}_external_cash_flow_yearly"
        self._attr_has_entity_name = True
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._previous_balance: float | None = None
        self._yearly_flow: float = 0.0
        self._attr_entity_registry_enabled_default = False

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
        """Return yearly cumulative positive cash flow for external total."""
        current_balance = self.coordinator.data.get("uncategorized_external_balance")

        if current_balance is None:
            return None

        if self._previous_balance is not None:
            change = current_balance - self._previous_balance
            if change > 0:
                self._yearly_flow += change

        self._previous_balance = current_balance
        return self._yearly_flow

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "period": "yearly",
            "source": "uncategorized_external_balance",
            "unit_of_measurement": CURRENCY_DOLLAR,
            "last_balance": self._previous_balance,
        }
