"""Unit tests for diagnostics.py."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.truenas_ce.diagnostics import (
    async_get_config_entry_diagnostics,
)

from ._fakes import make_coordinator


async def test_diagnostics_redacts_sensitive_fields_and_includes_data() -> None:
    """Diagnostics redact password/host fields while keeping coordinator data."""
    coordinator = make_coordinator(data={"system_info": {"version": "25.10.4"}})
    coordinator.config_entry.data["password"] = "s3cr3t"
    coordinator.config_entry.options = {"host": "truenas.local"}
    entry = SimpleNamespace(
        data=coordinator.config_entry.data,
        options=coordinator.config_entry.options,
        runtime_data=coordinator,
    )

    result = await async_get_config_entry_diagnostics(SimpleNamespace(), entry)

    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["entry"]["options"]["host"] == "**REDACTED**"
    assert result["data"]["system_info"]["version"] == "25.10.4"


async def test_diagnostics_no_coordinator_returns_empty_data() -> None:
    """Diagnostics return empty data when the entry has no runtime coordinator."""
    entry = SimpleNamespace(data={}, options={}, runtime_data=None)

    result = await async_get_config_entry_diagnostics(SimpleNamespace(), entry)

    assert not result["data"]
