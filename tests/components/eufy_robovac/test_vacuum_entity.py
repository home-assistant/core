"""Tests for Eufy RoboVac vacuum entity."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.components.vacuum import VacuumActivity

from homeassistant.components.eufy_robovac.local_api import EufyRoboVacLocalApiError
from homeassistant.components.eufy_robovac.model_mappings import MODEL_MAPPINGS
from homeassistant.components.eufy_robovac.vacuum import EufyRoboVacEntity


class _FakeApi:
    """Fake local API client used by tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.dps: dict[str, Any] = {
            "15": "standby",
            "102": "Standard",
            "104": 65,
            "106": "0",
        }

    async def async_send_dps(self, hass, dps: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(dps)
        return {"success": True}

    async def async_get_dps(self, hass) -> dict[str, Any]:
        return self.dps


@pytest.fixture
def entity(hass) -> EufyRoboVacEntity:
    """Create a test entity with fake API."""
    entry = SimpleNamespace(
        data={
            "name": "Hall Vacuum",
            "model": "T2253",
            "host": "192.168.1.50",
            "id": "abc123",
            "local_key": "abcdefghijklmnop",
            "protocol_version": "3.3",
        },
        runtime_data={"dps": {}},
        entry_id="test_entry_id",
    )
    vacuum = EufyRoboVacEntity(entry=entry, mapping=MODEL_MAPPINGS["T2253"])
    vacuum._api = _FakeApi()
    vacuum._hass = hass
    return vacuum


@pytest.mark.asyncio
async def test_async_start_sends_auto_mode(entity: EufyRoboVacEntity) -> None:
    """Starting should send DPS 2 True for T2253."""
    await entity.async_start()
    assert entity._api.sent[-1] == {"2": True}


@pytest.mark.asyncio
async def test_async_pause_sends_pause_command(entity: EufyRoboVacEntity) -> None:
    """Pausing should send DPS 2 False for T2253."""
    await entity.async_pause()
    assert entity._api.sent[-1] == {"2": False}


@pytest.mark.asyncio
async def test_async_return_to_base_sends_return(entity: EufyRoboVacEntity) -> None:
    """Return to base should send DPS 101 True for T2253."""
    await entity.async_return_to_base()
    assert entity._api.sent[-1] == {"101": True}


@pytest.mark.asyncio
async def test_async_update_maps_activity_and_battery(entity: EufyRoboVacEntity) -> None:
    """Update should map standby status and fan speed."""
    await entity.async_update()

    assert entity.activity == VacuumActivity.IDLE
    assert "dps" not in entity.extra_state_attributes
    assert entity.fan_speed == "standard"
    assert entity.extra_state_attributes["status_raw"] == "standby"


@pytest.mark.asyncio
async def test_async_update_marks_entity_unavailable_on_error(
    entity: EufyRoboVacEntity,
) -> None:
    """Polling errors should mark the entity unavailable."""

    async def _raise_error(_hass):
        raise EufyRoboVacLocalApiError("boom")

    entity._api.async_get_dps = _raise_error
    await entity.async_update()

    assert entity.available is False


@pytest.mark.asyncio
async def test_async_update_marks_entity_unavailable_on_empty_dps(
    entity: EufyRoboVacEntity,
) -> None:
    """Empty DPS payloads should mark the entity unavailable."""
    entity._api.dps = {}

    await entity.async_update()

    assert entity.available is False


@pytest.mark.asyncio
async def test_async_update_normalizes_no_error_variants(
    entity: EufyRoboVacEntity,
) -> None:
    """Error value 'no error' should not force ERROR activity."""
    entity._api.dps = {
        "15": "standby",
        "102": "Standard",
        "104": 65,
        "106": "no error",
    }

    await entity.async_update()

    assert entity.activity == VacuumActivity.IDLE
