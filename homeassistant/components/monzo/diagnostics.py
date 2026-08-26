"""Diagnostics support for Monzo."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .const import CONF_CLOUDHOOK_URL, CONF_WEBHOOK_URL, NON_TRANSFER_ACCOUNT_TYPES
from .coordinator import MonzoConfigEntry

TO_REDACT = {
    CONF_CLOUDHOOK_URL,
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    CONF_WEBHOOK_URL,
    "entry_id",
    "profile",
    "title",
    "unique_id",
}


def _account_diagnostics(account: dict[str, Any]) -> dict[str, Any]:
    """Return privacy-safe diagnostics for an account."""
    account_type = account.get("type")
    balance = account.get("balance")
    owners = account.get("owners")

    return {
        "type": account_type,
        "currency": balance.get("currency") if isinstance(balance, Mapping) else None,
        "owner_count": len(owners) if isinstance(owners, list) else None,
        "transfer_allowed_by_integration": account_type is not None
        and account_type not in NON_TRANSFER_ACCOUNT_TYPES,
        "available_fields": sorted(account),
        "balance_fields": sorted(balance) if isinstance(balance, Mapping) else [],
    }


def _pot_diagnostics(pot: dict[str, Any], account_ids: set[str]) -> dict[str, Any]:
    """Return privacy-safe diagnostics for a pot."""
    return {
        "type": pot.get("type"),
        "style": pot.get("style"),
        "currency": pot.get("currency"),
        "linked_account_present": pot.get("current_account_id") in account_ids,
        "available_fields": sorted(pot),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MonzoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    coordinator = runtime_data.coordinator
    data = coordinator.data
    last_exception = coordinator.last_exception
    account_ids = set(data.accounts)

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception_type": (
                type(last_exception).__name__ if last_exception is not None else None
            ),
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "account_count": len(data.accounts),
            "pot_count": len(data.pots),
            "accounts": [
                _account_diagnostics(account) for account in data.accounts.values()
            ],
            "pots": [_pot_diagnostics(pot, account_ids) for pot in data.pots.values()],
        },
        "webhook": {
            "has_persisted_webhook_url": CONF_WEBHOOK_URL in entry.data,
            **runtime_data.webhook_manager.diagnostics_data,
        },
    }
