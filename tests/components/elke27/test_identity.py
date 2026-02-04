"""Tests for Elke27 identity helpers."""

from __future__ import annotations

import socket

import pytest

from homeassistant.components.elke27 import identity as identity_module
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_async_get_integration_serial_existing(
    hass: HomeAssistant,
) -> None:
    """Verify existing serial is returned without extra work."""
    serial = await identity_module.async_get_integration_serial(
        hass, "host", existing="1234"
    )
    assert serial == "1234"


async def test_async_get_integration_serial_uses_mac(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify MAC-based serial is used when available."""
    monkeypatch.setattr(identity_module, "_resolve_host", lambda host: "1.2.3.4")
    async def _get_source_ip(*_args, **_kwargs):
        return "1.2.3.4"

    monkeypatch.setattr(identity_module.network, "async_get_source_ip", _get_source_ip)
    monkeypatch.setattr(identity_module, "_get_mac_for_source_ip", lambda *_: "AA:BB")
    serial = await identity_module.async_get_integration_serial(hass, "host")
    assert serial == "aabb"


async def test_async_get_integration_serial_falls_back(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify serial generation when networking fails."""
    monkeypatch.setattr(identity_module, "_resolve_host", lambda host: "1.2.3.4")

    async def _raise(*_args, **_kwargs):
        raise HomeAssistantError

    monkeypatch.setattr(identity_module.network, "async_get_source_ip", _raise)
    serial = await identity_module.async_get_integration_serial(hass, "host")
    assert len(serial) == identity_module.INTEGRATION_SERIAL_LENGTH
    assert serial.isdigit()


def test_resolve_host_handles_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify host resolution returns host on error."""
    def _raise(*_args, **_kwargs):
        raise OSError

    monkeypatch.setattr(socket, "gethostbyname", _raise)
    assert identity_module._resolve_host("example.com") == "example.com"


def test_extract_mac_none_when_missing() -> None:
    """Verify MAC extraction returns None for unsupported families."""
    addrs = [type("Addr", (), {"family": object(), "address": "x"})()]
    assert identity_module._extract_mac(addrs) is None


def test_extract_mac_supported_family(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify MAC extraction for supported families."""
    family = getattr(socket, "AF_PACKET", None) or getattr(socket, "AF_LINK", None)
    if family is None:
        pytest.skip("No supported MAC family on this platform")
    addrs = [type("Addr", (), {"family": family, "address": "aa:bb:cc:dd:ee:ff"})()]
    assert identity_module._extract_mac(addrs) == "aa:bb:cc:dd:ee:ff"


async def test_get_mac_for_source_ip_handles_errors(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify MAC lookup handles psutil errors and missing MACs."""
    class FakePsutil:
        def __init__(self, exc: Exception | None = None) -> None:
            self._exc = exc
        def net_if_addrs(self):  # type: ignore[no-untyped-def]
            if self._exc:
                raise self._exc
            return {
                "eth0": [
                    type("Addr", (), {"address": "1.2.3.4", "family": object()})()
                ]
            }

    class FakeWrapper:
        def __init__(self, exc: Exception | None = None) -> None:
            self.psutil = FakePsutil(exc)

    monkeypatch.setattr(identity_module.ha_psutil, "PsutilWrapper", lambda: FakeWrapper(OSError()))
    assert identity_module._get_mac_for_source_ip("1.2.3.4") is None

    monkeypatch.setattr(identity_module.ha_psutil, "PsutilWrapper", lambda: FakeWrapper(None))
    assert identity_module._get_mac_for_source_ip("1.2.3.4") is None


async def test_integration_serial_no_source_ip(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify serial generation when source IP is missing."""
    async def _get_source_ip(*_args, **_kwargs):
        return None

    monkeypatch.setattr(identity_module.network, "async_get_source_ip", _get_source_ip)
    serial = await identity_module.async_get_integration_serial(hass, "host")
    assert len(serial) == identity_module.INTEGRATION_SERIAL_LENGTH


def test_normalize_serial_and_identity() -> None:
    """Verify serial normalization and identity payload."""
    assert identity_module._normalize_serial("AA:bb-11") == "aabb11"
    identity = identity_module.build_client_identity("112233")
    assert identity == {"mn": str(identity_module.MANUFACTURER_NUMBER), "sn": "112233"}
