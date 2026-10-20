"""Tests for the SmartThings app ledger."""

from typing import Any

from homeassistant.components.smartthings.app_ledger import (
    STORAGE_KEY,
    async_get_app_ledger,
)
from homeassistant.core import HomeAssistant


async def test_record(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test recording app ids persists correctly."""
    ledger = await async_get_app_ledger(hass)

    await ledger.async_record("app-1")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1"]

    # Recording the same id again is a no-op, not a duplicate.
    await ledger.async_record("app-1")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1"]

    await ledger.async_record("app-2")
    assert hass_storage[STORAGE_KEY]["data"]["app_ids"] == ["app-1", "app-2"]


async def test_get_app_ledger_is_a_singleton(hass: HomeAssistant) -> None:
    """Test the same ledger instance is returned for a given hass."""
    ledger1 = await async_get_app_ledger(hass)
    ledger2 = await async_get_app_ledger(hass)
    assert ledger1 is ledger2
