"""Event platform for the Monzo integration."""

from typing import Any, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_DATA,
    DEVICE_MODEL_ACCOUNT,
    DOMAIN,
    EVENT_TRANSACTION_CREATED,
    NON_TRANSFER_ACCOUNT_TYPES,
)
from .coordinator import MonzoConfigEntry
from .helpers import get_account_name
from .webhook import webhook_signal

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonzoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up transaction events and discover new accounts."""
    coordinator = config_entry.runtime_data.coordinator
    known_account_ids: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add transaction events for newly discovered accounts."""
        current_account_ids = set(coordinator.data.accounts)
        known_account_ids.intersection_update(current_account_ids)
        new_account_ids = current_account_ids - known_account_ids
        if not new_account_ids:
            return
        async_add_entities(
            MonzoTransactionEvent(coordinator.data.accounts[account_id])
            for account_id in sorted(new_account_ids)
        )
        known_account_ids.update(new_account_ids)

    _async_add_new_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_entities)
    )


class MonzoTransactionEvent(EventEntity):
    """Represent transaction events for a Monzo account."""

    _attr_attribution = "Data provided by Monzo"
    _attr_event_types = [EVENT_TRANSACTION_CREATED]
    _attr_has_entity_name = True
    _attr_translation_key = "transaction"

    def __init__(self, account: dict[str, Any]) -> None:
        """Initialize the event entity."""
        self._account_id = account["id"]
        self._attr_unique_id = f"{self._account_id}_transaction"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._account_id)},
            manufacturer="Monzo",
            model=(
                account["name"]
                if account["type"] in NON_TRANSFER_ACCOUNT_TYPES
                else DEVICE_MODEL_ACCOUNT
            ),
            name=get_account_name(account),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to transaction webhooks for this account."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                webhook_signal(self._account_id),
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event_type: str, transaction: dict[str, Any]) -> None:
        """Handle a Monzo transaction event."""
        self._trigger_event(event_type, {ATTR_DATA: transaction})
        self.async_write_ha_state()
