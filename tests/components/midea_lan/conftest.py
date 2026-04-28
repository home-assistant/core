"""Fixtures for Midea LAN tests."""

from __future__ import annotations

import pytest

from homeassistant.components.midea_lan.config_flow import MideaLanConfigFlow
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_flow(hass: HomeAssistant) -> MideaLanConfigFlow:
    """Return a configured config flow instance."""
    config_flow = MideaLanConfigFlow()
    config_flow.hass = hass
    return config_flow


@pytest.fixture
def mock_device_config_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict]:
    """Mock config-flow storage I/O in memory without creating files."""
    storage: dict[str, dict] = {}

    async def fake_async_save(self, data: dict) -> None:
        storage[self.key] = data.copy()

    async def fake_async_load(self) -> dict | None:
        return storage.get(self.key)

    monkeypatch.setattr(
        "homeassistant.components.midea_lan.config_flow.Store.async_save",
        fake_async_save,
    )
    monkeypatch.setattr(
        "homeassistant.components.midea_lan.config_flow.Store.async_load",
        fake_async_load,
    )
    return storage
