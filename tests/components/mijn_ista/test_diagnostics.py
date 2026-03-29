"""Tests for mijn_ista diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.mijn_ista.coordinator import _parse_customer
from custom_components.mijn_ista.diagnostics import async_get_config_entry_diagnostics

from .conftest import MOCK_AVG_VALUES, MOCK_MONTH_VALUES, MOCK_USER_VALUES


def _make_entry_with_coordinator(hass):
    """Return a mock config entry with a loaded coordinator."""
    customer = _parse_customer(
        MOCK_USER_VALUES["Cus"][0], MOCK_MONTH_VALUES, MOCK_AVG_VALUES
    )
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"test-cuid-abc123": customer}

    entry = MagicMock()
    entry.title = "ista NL — Test User"
    entry.data = {"username": "test@example.com", "password": "s3cr3t"}
    entry.options = {"update_interval": 24}
    entry.runtime_data = coordinator
    return entry


class TestDiagnostics:
    async def test_returns_dict(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        assert isinstance(result, dict)

    async def test_password_is_redacted(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["entry"]["data"]["password"] == "**REDACTED**"

    async def test_username_is_redacted(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["entry"]["data"]["username"] == "**REDACTED**"

    async def test_coordinator_structure_present(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        coord = result["coordinator"]
        assert coord["last_update_success"] is True
        assert len(coord["properties"]) == 1

    async def test_property_contains_service_info(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        props = result["coordinator"]["properties"]
        prop = next(iter(props.values()))
        assert "services" in prop
        assert "monthly_entries" in prop
        assert prop["monthly_entries"] == 2

    async def test_property_key_is_truncated_cuid(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        result = await async_get_config_entry_diagnostics(hass, entry)
        props = result["coordinator"]["properties"]
        key = next(iter(props.keys()))
        # Should be 8 chars + ellipsis, not the full CUID
        assert key.endswith("…")
        assert len(key) == 9

    async def test_empty_coordinator_data(self, hass: HomeAssistant):
        entry = _make_entry_with_coordinator(hass)
        entry.runtime_data.data = None
        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["coordinator"]["properties"] == {}
