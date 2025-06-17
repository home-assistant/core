"""Base entity for Firefly III integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from yarl import URL

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import FireflyDataUpdateCoordinator


class FireflyBaseEntity(CoordinatorEntity[FireflyDataUpdateCoordinator]):
    """Base class for Firefly III entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a Firefly entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=coordinator.config_entry.data[CONF_HOST],
            configuration_url=URL(coordinator.config_entry.data[CONF_HOST]),
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )


class FireflyAccountEntity(FireflyBaseEntity):
    """Entity for Firefly III account."""

    def __init__(self, coordinator, entity_description, account) -> None:
        """Initialize Firefly account entity."""
        super().__init__(coordinator, entity_description)
        self._account = account
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_description.key}_{account.id}"
        self._attr_name = account.attributes.name
        account_type = account.attributes.type
        if account_type == "expense":
            self._attr_icon = "mdi:cash-minus"
        elif account_type == "asset":
            self._attr_icon = "mdi:account-cash"
        elif account_type == "revenue":
            self._attr_icon = "mdi:cash-plus"
        elif account_type == "liabilities":
            self._attr_icon = "mdi:hand-coin"
        else:
            self._attr_icon = "mdi:bank"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes for the account entity."""
        return {
            "account_role": self._account.attributes.account_role,
            "currency_code": self._account.attributes.native_currency_code,
        }

    @property
    def native_value(self) -> float | None:
        """Return the native value for the account entity."""
        return self._account.attributes.current_balance


class FireflyBudgetEntity(FireflyBaseEntity):
    """Entity for Firefly III budget."""

    def __init__(self, budget, coordinator) -> None:
        """Initialize Firefly budget entity."""
        super().__init__(coordinator)
        self._budget = budget

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes for the budget entity."""
        return {
            "budget_amount": self._budget.amount,
            "budget_category": self._budget.category,
        }
