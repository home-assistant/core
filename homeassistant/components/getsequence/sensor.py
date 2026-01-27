"""Sensor platform for Sequence integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SequenceDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sequence sensor entities."""
    coordinator: SequenceDataUpdateCoordinator = entry.runtime_data

    # Create a balance sensor for each account
    entities = [
        SequenceAccountSensor(coordinator, entry, account)
        for account in coordinator.data
    ]

    async_add_entities(entities)


class SequenceAccountSensor(
    CoordinatorEntity[SequenceDataUpdateCoordinator], SensorEntity
):
    """Representation of a Sequence account balance sensor."""

    _attr_has_entity_name = True
    _attr_name = "Balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: SequenceDataUpdateCoordinator,
        entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.account_id = account["id"]
        self.account_name = account["name"]
        self._attr_unique_id = f"{entry.entry_id}_{self.account_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.account_id)},
            name=f"{entry.data[CONF_NAME]} - {self.account_name}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> float | None:
        """Return the balance of the account."""
        account = self._get_account_data()
        if account is None:
            return None
        return account.get("balance", {}).get("amountInDollars")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        account = self._get_account_data()
        if account is None:
            return False
        return account.get("balance", {}).get("amountInDollars") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        account = self._get_account_data()
        if account is None:
            return {}

        attrs = {k: v for k, v in account.items() if k != "balance"}
        if error := account.get("balance", {}).get("displayMessage"):
            attrs["balance_error"] = error
        return attrs

    def _get_account_data(self) -> dict[str, Any] | None:
        """Get the current account data from coordinator."""
        for account in self.coordinator.data:
            if account["id"] == self.account_id:
                return account
        return None
