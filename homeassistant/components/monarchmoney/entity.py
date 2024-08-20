"""Monarch money entity definition."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MonarchMoneyDataUpdateCoordinator


class MonarchMoneyEntityBase(CoordinatorEntity[MonarchMoneyDataUpdateCoordinator]):
    """Base entity for Monarch Money with entity name attribute."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MonarchMoneyDataUpdateCoordinator) -> None:
        """Initialize the Monarch Money Entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator


class MonarchMoneyCashFlowEntity(MonarchMoneyEntityBase):
    """Custom entity for Cashflow sensors."""

    def __init__(
        self,
        coordinator: MonarchMoneyDataUpdateCoordinator,
        description: EntityDescription,
        data: Any,
    ) -> None:
        """Initialize the Monarch Money Entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.subscription_id}_cashflow_{description.key}"
        )
        self._data = data
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "monarch_money_cashflow")},
            name="Cashflow",
            suggested_area="Banking/Finance",
        )

    @property
    def summary_data(self) -> Any:
        """Return cashflow summary data."""
        return self.coordinator.cashflow_summary


class MonarchMoneyAccountEntity(MonarchMoneyEntityBase):
    """Define a generic class for Entities."""

    def __init__(
        self,
        coordinator: MonarchMoneyDataUpdateCoordinator,
        description: EntityDescription,
        account: Any,
    ) -> None:
        """Initialize the Monarch Money Entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._account_id = account["id"]

        # Parse out some fields
        institution = "Manual entry"
        configuration_url = "http://monarchmoney.com"
        if account.get("institution") is not None:
            institution = account["institution"].get("name", "Manual entry")
            configuration_url = account["institution"]["url"]

        provider = account.get("dataProvider", "Manual input")
        if account.get("credential") is not None:
            provider = account["credential"].get("dataProvider", provider)

        self._attr_attribution = f"Data provided by Monarch Money API via {provider}"

        if not configuration_url.startswith(("http://", "https://")):
            configuration_url = f"http://{configuration_url}"

        self._attr_unique_id = f"{coordinator.subscription_id}_{account['displayName']}_{description.translation_key}"

        atype = account["type"]["display"]
        asubtype = account["subtype"]["display"]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account["id"])},
            name=f"{institution} {account['displayName']}",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=provider,
            model=f"{institution} - {atype} - {asubtype}",
            configuration_url=configuration_url,
            suggested_area="Banking/Finance",
        )

    @property
    def account_data(self) -> Any:
        """Return the account data."""
        return self.coordinator.get_account_for_id(self._account_id)
