"""Base entity for Firefly III integration."""

from __future__ import annotations

from pyfirefly.models import Account, Budget, Category
from yarl import URL

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import FireflyDataUpdateCoordinator


class FireflyBaseEntity(CoordinatorEntity[FireflyDataUpdateCoordinator]):
    """Base class for Firefly III entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
    ) -> None:
        """Initialize a Firefly entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name=NAME,
            configuration_url=URL(coordinator.config_entry.data[CONF_URL]),
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_service")},
        )


class FireflyAccountBaseEntity(FireflyBaseEntity):
    """Base class for Firefly III account entity."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        account: Account,
        key: str,
    ) -> None:
        """Initialize a Firefly account entity."""
        super().__init__(coordinator)
        self._account = account
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name=account.attributes.name,
            configuration_url=f"{URL(coordinator.config_entry.data[CONF_URL])}/accounts/show/{account.id}",
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_account_{account.id}")
            },
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_account_{account.id}_{key}"
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for account in self.coordinator.data.accounts:
            if account.id == self._account.id:
                self._account = account
                break
        super()._handle_coordinator_update()


class FireflyCategoryBaseEntity(FireflyBaseEntity):
    """Base class for Firefly III category entity."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        category: Category,
        key: str,
    ) -> None:
        """Initialize a Firefly category entity."""
        super().__init__(coordinator)
        self._category = category
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name=category.attributes.name,
            configuration_url=f"{URL(coordinator.config_entry.data[CONF_URL])}/categories/show/{category.id}",
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_category_{category.id}")
            },
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_category_{category.id}_{key}"
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for category in self.coordinator.data.category_details:
            if category.id == self._category.id:
                self._category = category
                break
        super()._handle_coordinator_update()


class FireflyBudgetBaseEntity(FireflyBaseEntity):
    """Base class for Firefly III budget entity."""

    def __init__(
        self,
        coordinator: FireflyDataUpdateCoordinator,
        budget: Budget,
        key: str,
    ) -> None:
        """Initialize a Firefly budget entity."""
        super().__init__(coordinator)
        self._budget = budget
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name=budget.attributes.name,
            configuration_url=f"{URL(coordinator.config_entry.data[CONF_URL])}/budgets/show/{budget.id}",
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_budget_{budget.id}")
            },
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_budget_{budget.id}_{key}"
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for budget in self.coordinator.data.budgets:
            if budget.id == self._budget.id:
                self._budget = budget
                break
        super()._handle_coordinator_update()
