"""Tests for Eufy RoboVac local API wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.components.eufy_robovac.local_api import (
    EufyRoboVacLocalApi,
    EufyRoboVacLocalApiError,
)


@dataclass
class _FakeDevice:
    """Fake tinytuya device used by tests."""

    dev_id: str
    address: str
    local_key: str
    persist: bool

    version: float | None = None
    timeout: float | None = None
    closed: bool = False
    last_dps: dict[str, Any] | None = None

    def set_version(self, version: float) -> None:
        self.version = version

    def set_socketTimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def set_multiple_values(self, dps: dict[str, Any]) -> dict[str, Any]:
        self.last_dps = dps
        return {"success": True, "dps": dps}

    def status(self) -> dict[str, Any]:
        return {"dps": {"15": "standby", "104": 88}}

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_tinytuya(monkeypatch: pytest.MonkeyPatch) -> list[_FakeDevice]:
    """Provide a fake tinytuya module and capture device instances."""
    created: list[_FakeDevice] = []

    def _factory(
        *, dev_id: str, address: str, local_key: str, persist: bool
    ) -> _FakeDevice:
        device = _FakeDevice(
            dev_id=dev_id,
            address=address,
            local_key=local_key,
            persist=persist,
        )
        created.append(device)
        return device

    monkeypatch.setitem(
        __import__("sys").modules, "tinytuya", SimpleNamespace(Device=_factory)
    )
    return created


@pytest.mark.asyncio
async def test_async_send_dps_uses_tinytuya_device(
    hass,
    fake_tinytuya: list[_FakeDevice],
) -> None:
    """Sending DPS should create and configure a tinytuya device."""
    api = EufyRoboVacLocalApi(
        host="192.168.1.99",
        device_id="abc123",
        local_key="abcdefghijklmnop",
        protocol_version="3.3",
    )

    result = await api.async_send_dps(hass, {"5": "Auto"})

    assert result["success"] is True
    assert len(fake_tinytuya) == 1
    device = fake_tinytuya[0]
    assert device.dev_id == "abc123"
    assert device.address == "192.168.1.99"
    assert device.local_key == "abcdefghijklmnop"
    assert device.version == 3.3
    assert device.timeout == 5.0
    assert device.last_dps == {"5": "Auto"}
    assert device.closed is True


@pytest.mark.asyncio
async def test_async_get_dps_returns_dps_payload(
    hass,
    fake_tinytuya: list[_FakeDevice],
) -> None:
    """Status reads should return normalized DPS keys."""
    api = EufyRoboVacLocalApi(
        host="192.168.1.99",
        device_id="abc123",
        local_key="abcdefghijklmnop",
        protocol_version="3.3",
    )

    dps = await api.async_get_dps(hass)

    assert dps == {"15": "standby", "104": 88}
    assert fake_tinytuya[0].closed is True


@pytest.mark.asyncio
async def test_async_send_dps_closes_device_on_error(hass, monkeypatch) -> None:
    """Send failures should still close the tinytuya device."""
    created: list[_FakeDevice] = []

    class _RaisingSendDevice(_FakeDevice):
        def set_multiple_values(self, dps: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("send failed")

    def _factory(
        *, dev_id: str, address: str, local_key: str, persist: bool
    ) -> _RaisingSendDevice:
        device = _RaisingSendDevice(
            dev_id=dev_id,
            address=address,
            local_key=local_key,
            persist=persist,
        )
        created.append(device)
        return device

    monkeypatch.setitem(
        __import__("sys").modules, "tinytuya", SimpleNamespace(Device=_factory)
    )

    api = EufyRoboVacLocalApi(
        host="192.168.1.99",
        device_id="abc123",
        local_key="abcdefghijklmnop",
        protocol_version="3.3",
    )

    with pytest.raises(EufyRoboVacLocalApiError):
        await api.async_send_dps(hass, {"5": "Auto"})

    assert created[0].closed is True


@pytest.mark.asyncio
async def test_async_get_dps_closes_device_on_error(hass, monkeypatch) -> None:
    """Status failures should still close the tinytuya device."""
    created: list[_FakeDevice] = []

    class _RaisingStatusDevice(_FakeDevice):
        def status(self) -> dict[str, Any]:
            raise RuntimeError("status failed")

    def _factory(
        *, dev_id: str, address: str, local_key: str, persist: bool
    ) -> _RaisingStatusDevice:
        device = _RaisingStatusDevice(
            dev_id=dev_id,
            address=address,
            local_key=local_key,
            persist=persist,
        )
        created.append(device)
        return device

    monkeypatch.setitem(
        __import__("sys").modules, "tinytuya", SimpleNamespace(Device=_factory)
    )

    api = EufyRoboVacLocalApi(
        host="192.168.1.99",
        device_id="abc123",
        local_key="abcdefghijklmnop",
        protocol_version="3.3",
    )

    with pytest.raises(EufyRoboVacLocalApiError):
        await api.async_get_dps(hass)

    assert created[0].closed is True
