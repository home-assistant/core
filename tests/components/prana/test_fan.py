"""Tests for Prana fan entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.prana.const import DOMAIN, PranaFanType
from homeassistant.components.prana.fan import PranaFan
from homeassistant.core import HomeAssistant


# --- New: stub aiohttp to avoid real network ---
@pytest.fixture(autouse=True)
def _patch_aiohttp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ClientSession in fan.py to avoid real HTTP."""

    class _DummyResponse:
        def __init__(self, status: int = 200) -> None:
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def text(self) -> str:
            return ""

        async def json(self) -> dict:
            return {}

    class _MockClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        # Important: return an async context manager directly (not a coroutine)
        def post(self, url, **kwargs):
            return _DummyResponse(200)

    # fan.py does `from aiohttp import ClientSession`
    monkeypatch.setattr(
        "homeassistant.components.prana.fan.ClientSession",
        _MockClientSession,
        raising=False,
    )


@pytest.fixture(autouse=True)
def _patch_senders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch command senders used inside fan entity."""
    # Patch PranaSendSpeed methods in fan module
    monkeypatch.setattr(
        "homeassistant.components.prana.fan.PranaSendSpeed.send_speed_percentage",
        AsyncMock(return_value=None),
        raising=False,
    )
    monkeypatch.setattr(
        "homeassistant.components.prana.fan.PranaSendSpeed.send_speed_is_on",
        AsyncMock(return_value=None),
        raising=False,
    )
    monkeypatch.setattr(
        "homeassistant.components.prana.fan.PranaSendSpeed.send",
        AsyncMock(return_value=None),
        raising=False,
    )
    # Patch PranaSendSwitch.send (used for preset modes)
    monkeypatch.setattr(
        "homeassistant.components.prana.fan.PranaSendSwitch.send",
        AsyncMock(return_value=None),
        raising=False,
    )


@pytest.fixture
def coordinator(hass: HomeAssistant):
    """Fake coordinator for tests."""
    coord = MagicMock()
    coord.data = {
        PranaFanType.EXTRACT: {"is_on": False, "speed": 3, "max_speed": 10},
        PranaFanType.SUPPLY: {"is_on": True, "speed": 5, "max_speed": 10},
    }
    coord.max_speed = 10  # required by PranaFan.percentage calculations
    coord.async_refresh = AsyncMock()
    coord.last_update_success = True
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    return coord


@pytest.fixture
def config_entry(hass: HomeAssistant):
    """Fake config_entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"host": "127.0.0.1", "name": "Prana Device"}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    return entry


def test_get_icon_extract(coordinator, config_entry) -> None:
    """Check icon and availability for extract fan."""
    fan = PranaFan("id1", "Extract", coordinator, PranaFanType.EXTRACT, config_entry)
    # Ensure entity name property does not try to access platform metadata in tests
    assert fan.icon == "mdi:arrow-expand-right"
    assert fan.available is True


def test_get_icon_supply(coordinator, config_entry) -> None:
    """Check icon and availability for supply fan."""
    fan = PranaFan("id2", "Supply", coordinator, PranaFanType.SUPPLY, config_entry)
    # Ensure entity name property does not try to access platform metadata in tests
    fan._attr_name = "Supply"
    assert fan.icon == "mdi:arrow-expand-left"
    # percentage is speed * (100 // max_speed) -> 5 * (100 // 10) == 50
    assert fan.percentage == 50
    assert fan.is_on is True


@pytest.mark.asyncio
async def test_turn_on_and_off(hass: HomeAssistant, coordinator, config_entry) -> None:
    """Test turning fan on and off."""
    fan = PranaFan("id3", "Extract", coordinator, PranaFanType.EXTRACT, config_entry)
    # Prevent name lookup into platform metadata during async operations
    fan._attr_name = "Extract"
    # Bind hass and entity_id so async_write_ha_state works
    fan.hass = hass
    fan.entity_id = "fan.prana_test_extract"
    # Bind entry on coordinator so URL builder uses real host string
    coordinator.entry = config_entry

    # Initially off
    coordinator.data = {
        PranaFanType.EXTRACT: {"is_on": False, "speed": 0, "max_speed": 10}
    }
    coordinator.max_speed = 10
    assert fan.is_on is False
    assert fan.percentage == 0

    # Turn on -> expect send_speed_is_on called and refresh
    await fan.async_turn_on()
    assert coordinator.async_refresh.await_count >= 1

    # Simulate device state after refresh
    coordinator.data = {
        PranaFanType.EXTRACT: {"is_on": True, "speed": 10, "max_speed": 10}
    }
    assert fan.is_on is True
    assert fan.percentage == 100

    # Turn off -> expect send_speed_is_on called and refresh
    await fan.async_turn_off()
    assert coordinator.async_refresh.await_count >= 2

    # Simulate device state after refresh
    coordinator.data = {
        PranaFanType.EXTRACT: {"is_on": False, "speed": 0, "max_speed": 10}
    }
    assert fan.is_on is False
    assert fan.percentage == 0


@pytest.mark.asyncio
async def test_set_percentage(hass: HomeAssistant, coordinator, config_entry) -> None:
    """Test setting fan speed as percentage."""
    fan = PranaFan("id4", "Extract", coordinator, PranaFanType.EXTRACT, config_entry)
    # Prevent name lookup into platform metadata during async operations
    fan._attr_name = "Extract"
    # Bind hass and entity_id so async_write_ha_state works
    fan.hass = hass
    fan.entity_id = "fan.prana_test_extract_2"
    # Bind entry on coordinator so URL builder uses real host string
    coordinator.entry = config_entry
    coordinator.max_speed = 10

    coordinator.data = {
        PranaFanType.EXTRACT: {"is_on": False, "speed": 0, "max_speed": 10}
    }
    assert fan.percentage == 0

    # Set 70% -> expect refresh
    await fan.async_set_percentage(70)
    coordinator.async_refresh.assert_awaited()

    # Simulate device state after refresh
    coordinator.data = {
        PranaFanType.EXTRACT: {"is_on": True, "speed": 7, "max_speed": 10}
    }
    assert fan.percentage == 70
    assert fan.is_on is True
