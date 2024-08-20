"""Monarch money entity definition."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    MonarchAccount,
    MonarchCashflow,
    MonarchMoneyDataUpdateCoordinator,
)


class MonarchMoneyEntityBase(CoordinatorEntity[MonarchMoneyDataUpdateCoordinator]):
    """Base entity for Monarch Money with entity name attribute."""

    _attr_has_entity_name = True


class MonarchMoneyCashFlowEntity(MonarchMoneyEntityBase):
    """Custom entity for Cashflow sensors."""

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
            identifiers={(DOMAIN, "monarch_money_cashflow")},
            name="Cashflow",
            suggested_area="Banking/Finance",
        )

    @property
    def summary_data(self) -> MonarchCashflow:
        """Return cashflow summary data."""
        return self.coordinator.cashflow_summary


class MonarchMoneyAccountEntity(MonarchMoneyEntityBase):
    """Define a generic class for Entities."""

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

        # Parse out some fields
        institution = "Manual entry"
        if account.institution_name is not None:
            institution = account.institution_name
        configuration_url = "http://monarchmoney.com"
        if account.institution_url is not None:
            configuration_url = account.institution_url

        self._attr_attribution = (
            f"Data provided by Monarch Money API via {account.data_provider}"
        )

        if not configuration_url.startswith(("http://", "https://")):
            configuration_url = f"http://{configuration_url}"

        self._attr_unique_id = f"{coordinator.subscription_id}_{account.name}_{description.translation_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account.id)},
            name=f"{institution} {account.name}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=account.data_provider,
            model=f"{institution} - {account.type_name} - {account.subtype_name}",
            configuration_url=configuration_url,
            suggested_area="Banking/Finance",
        )

    @property
    def account_data(self) -> MonarchAccount:
        """Return the account data."""
        if account := self.coordinator.get_account_for_id(self._account_id):
            return account

        raise ValueError("Account not found")
