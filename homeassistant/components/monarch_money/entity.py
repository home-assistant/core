"""Monarch money entity definition."""

from typedmonarchmoney.models import MonarchAccount, MonarchCashflowSummary

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MonarchMoneyDataUpdateCoordinator


class MonarchMoneyEntityBase(CoordinatorEntity[MonarchMoneyDataUpdateCoordinator]):
    """Base entity for Monarch Money with entity name attribute."""

    _attr_has_entity_name = True


class MonarchMoneyCashFlowEntity(MonarchMoneyEntityBase):
    """Entity for Cashflow sensors."""

    def __init__(
        self,
        coordinator: MonarchMoneyDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the Monarch Money Entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.subscription_id}_cashflow_{description.key}"
        )
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.subscription_id))},
            name="Cashflow",
        )

    @property
    def summary_data(self) -> MonarchCashflowSummary:
        """Return cashflow summary data."""
        return self.coordinator.cashflow_summary


class MonarchMoneyAccountEntity(MonarchMoneyEntityBase):
    """Entity for Account Sensors."""

    def __init__(
        self,
        coordinator: MonarchMoneyDataUpdateCoordinator,
        description: EntityDescription,
        account: MonarchAccount,
    ) -> None:
        """Initialize the Monarch Money Entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._account_id = account.id
        self._attr_attribution = (
            f"Data provided by Monarch Money API via {account.data_provider}"
        )
        self._attr_unique_id = (
            f"{coordinator.subscription_id}_{account.id}_{description.translation_key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(account.id))},
            name=f"{account.institution_name} {account.name}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=account.data_provider,
            model=f"{account.institution_name} - {account.type_name} - {account.subtype_name}",
            configuration_url=account.institution_url,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and (
            self._account_id in self.coordinator.data.account_data
        )

    @property
    def account_data(self) -> MonarchAccount:
        """Return the account data."""
        return self.coordinator.data.account_data[self._account_id]
