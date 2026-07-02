"""Tests for diagnostics and repair helpers."""

from types import SimpleNamespace
from typing import Any, cast

from besen_bs20.models import BesenBS20Data, ChargerInfo
import pytest

from homeassistant.components.besen_bs20 import BesenBS20ConfigEntry, repairs
from homeassistant.components.besen_bs20.const import DOMAIN
from homeassistant.components.besen_bs20.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


def _diagnostics_entry() -> BesenBS20ConfigEntry:
    """Return a fake config entry for diagnostics."""

    state = BesenBS20Data(
        info=ChargerInfo(address="AA:BB", serial="SERIAL"),
        available=True,
        authenticated=True,
    )
    coordinator = SimpleNamespace(data=state, client=SimpleNamespace(state=state))
    return cast(
        BesenBS20ConfigEntry,
        SimpleNamespace(
            data={"address": "AA:BB", "pin": "123456"},
            options={"sync_clock": True},
            runtime_data=SimpleNamespace(coordinator=coordinator),
        ),
    )


@pytest.mark.asyncio
async def test_diagnostics_redacts_pin() -> None:
    """Diagnostics redact sensitive entry data."""

    diagnostics = await async_get_config_entry_diagnostics(
        cast(Any, object()),
        _diagnostics_entry(),
    )

    assert diagnostics["entry"]["data"]["pin"] == "**REDACTED**"
    assert diagnostics["state"]["available"] is True
    assert diagnostics["state"]["info"]["serial"] == "SERIAL"


def test_repair_issue_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repair helpers create and delete namespaced issues."""

    created: list[tuple[str, str, str, bool]] = []
    deleted: list[tuple[str, str]] = []

    def _create_issue(
        hass: HomeAssistant,
        domain: str,
        issue_id: str,
        *,
        is_fixable: bool,
        severity: object,
        translation_key: str,
    ) -> None:
        del hass, severity
        created.append((domain, issue_id, translation_key, is_fixable))

    def _delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
        del hass
        deleted.append((domain, issue_id))

    monkeypatch.setattr(ir, "async_create_issue", _create_issue)
    monkeypatch.setattr(ir, "async_delete_issue", _delete_issue)

    repairs.async_create_no_connectable_path_issue(cast(Any, object()), "entry")
    repairs.async_delete_no_connectable_path_issue(cast(Any, object()), "entry")

    assert created == [
        (DOMAIN, "entry_no_connectable_path", "no_connectable_path", False),
    ]
    assert deleted == [
        (DOMAIN, "entry_no_connectable_path"),
    ]
