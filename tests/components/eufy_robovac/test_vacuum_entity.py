"""Tests for Eufy RoboVac vacuum entity."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.components.vacuum import VacuumActivity

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
        }
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
    assert entity.extra_state_attributes["dps"]["104"] == 65
    assert entity.fan_speed == "standard"
