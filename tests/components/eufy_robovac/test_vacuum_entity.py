"""Tests for Eufy RoboVac vacuum entity."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

# pylint: disable-next=hass-component-root-import
from homeassistant.components.eufy_robovac import vacuum as vacuum_module

# pylint: disable-next=hass-component-root-import
from homeassistant.components.eufy_robovac.local_api import EufyRoboVacLocalApiError

# pylint: disable-next=hass-component-root-import
from homeassistant.components.eufy_robovac.model_mappings import MODEL_MAPPINGS

# pylint: disable-next=hass-component-root-import
from homeassistant.components.eufy_robovac.vacuum import EufyRoboVacEntity
from homeassistant.components.vacuum import VacuumActivity
from homeassistant.core import HomeAssistant


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

    async def async_send_dps(
        self, hass: HomeAssistant | None, dps: dict[str, Any]
    ) -> dict[str, Any]:
        self.sent.append(dps)
        return {"success": True}

    async def async_get_dps(self, hass: HomeAssistant | None) -> dict[str, Any]:
        return self.dps


@pytest.fixture
def entity(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> tuple[EufyRoboVacEntity, _FakeApi]:
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
    fake_api = _FakeApi()
    monkeypatch.setattr(vacuum_module, "EufyRoboVacLocalApi", lambda **kwargs: fake_api)
    vacuum = EufyRoboVacEntity(entry=entry, mapping=MODEL_MAPPINGS["T2253"])
    vacuum.hass = hass
    monkeypatch.setattr(vacuum, "async_write_ha_state", lambda: None)
    return vacuum, fake_api


async def test_async_start_sends_auto_mode(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Starting should send DPS 2 True for T2253."""
    vacuum, fake_api = entity
    await vacuum.async_start()
    assert fake_api.sent[-1] == {"2": True}


async def test_async_pause_sends_pause_command(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Pausing should send DPS 2 False for T2253."""
    vacuum, fake_api = entity
    await vacuum.async_pause()
    assert fake_api.sent[-1] == {"2": False}


async def test_async_return_to_base_sends_return(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Return to base should send DPS 101 True for T2253."""
    vacuum, fake_api = entity
    await vacuum.async_return_to_base()
    assert fake_api.sent[-1] == {"101": True}


async def test_async_update_maps_activity_and_battery(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Update should map standby status and fan speed."""
    vacuum, _fake_api = entity
    await vacuum.async_update()

    assert vacuum.activity == VacuumActivity.IDLE
    assert "dps" not in vacuum.extra_state_attributes
    assert vacuum.fan_speed == "standard"
    assert vacuum.extra_state_attributes["status_raw"] == "standby"


def test_primary_entity_uses_device_name(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Primary vacuum entity should rely on device naming."""
    vacuum, _fake_api = entity
    assert vacuum.has_entity_name is True
    assert vacuum.name is None
    assert vacuum.device_info["name"] == "Hall Vacuum"


async def test_async_update_marks_entity_unavailable_on_error(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Polling errors should mark the entity unavailable."""
    vacuum, fake_api = entity

    async def _raise_error(_hass: HomeAssistant | None) -> dict[str, Any]:
        raise EufyRoboVacLocalApiError("boom")

    fake_api.async_get_dps = _raise_error
    await vacuum.async_update()

    assert vacuum.available is False


async def test_async_update_marks_entity_unavailable_on_empty_dps(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Empty DPS payloads should mark the entity unavailable."""
    vacuum, fake_api = entity
    fake_api.dps = {}

    await vacuum.async_update()

    assert vacuum.available is False


async def test_async_update_normalizes_no_error_variants(
    entity: tuple[EufyRoboVacEntity, _FakeApi],
) -> None:
    """Error value 'no error' should not force ERROR activity."""
    vacuum, fake_api = entity
    fake_api.dps = {
        "15": "standby",
        "102": "Standard",
        "104": 65,
        "106": "no error",
    }

    await vacuum.async_update()

    assert vacuum.activity == VacuumActivity.IDLE
