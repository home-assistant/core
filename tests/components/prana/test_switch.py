"""Tests for the Prana switch platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.prana.const import DOMAIN, PranaSwitchType
from homeassistant.components.prana.switch import PranaSwitch, async_setup_entry
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def _patch_aiohttp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ClientSession in switch.py to avoid real HTTP."""

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

        def post(self, url, **kwargs):
            return _DummyResponse(200)

    monkeypatch.setattr(
        "homeassistant.components.prana.switch.ClientSession",
        _MockClientSession,
        raising=False,
    )


@pytest.fixture
def coordinator(hass: HomeAssistant):
    """Mock coordinator for tests."""
    coord = MagicMock()
    coord.data = {
        PranaSwitchType.BOUND: True,
        PranaSwitchType.HEATER: False,
        PranaSwitchType.WINTER: True,
        PranaSwitchType.AUTO: False,
        PranaSwitchType.AUTO_PLUS: True,
    }
    coord.async_refresh = AsyncMock()
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    return coord


@pytest.fixture
def config_entry(hass: HomeAssistant):
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_switch_entry"
    entry.data = {"host": "127.0.0.1", "name": "Prana Device"}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    return entry


async def test_switch_properties(
    coordinator: MagicMock, config_entry: MagicMock
) -> None:
    """Test switch entity properties."""
    bound_switch = PranaSwitch(
        "id1", "Bound", coordinator, "bound", PranaSwitchType.BOUND, config_entry
    )
    assert bound_switch.is_on is True
    assert bound_switch.icon == "mdi:link"

    heating = PranaSwitch(
        "id2", "Heater", coordinator, "heater", PranaSwitchType.HEATER, config_entry
    )
    assert heating.is_on is False
    assert heating.icon == "mdi:radiator"


@pytest.mark.asyncio
async def test_switch_turn_on_off(
    hass: HomeAssistant, coordinator: MagicMock, config_entry: MagicMock
) -> None:
    """Test turning switch on and off."""
    switch = PranaSwitch(
        "id3", "Winter", coordinator, "winter", PranaSwitchType.WINTER, config_entry
    )
    switch.hass = hass
    switch.entity_id = "switch.prana_winter"
    coordinator.entry = config_entry

    assert switch.is_on is True

    await switch.async_turn_off()
    assert coordinator.async_refresh.await_count >= 1
    coordinator.data[PranaSwitchType.WINTER] = False
    assert switch.is_on is False

    await switch.async_turn_on()
    assert coordinator.async_refresh.await_count >= 2
    coordinator.data[PranaSwitchType.WINTER] = True
    assert switch.is_on is True


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, coordinator: AsyncMock, config_entry: MagicMock
) -> None:
    """Test setup entry for switch platform."""
    coordinator = AsyncMock()
    coordinator.data = {
        PranaSwitchType.BOUND: True,
        PranaSwitchType.HEATER: False,
        PranaSwitchType.AUTO: True,
        PranaSwitchType.AUTO_PLUS: False,
        PranaSwitchType.WINTER: True,
    }
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    added = []

    def async_add_entities(entities):
        added.extend(entities)

    await async_setup_entry(hass, config_entry, async_add_entities)

    # The platform unconditionally adds 5 switches
    assert len(added) == 5
    assert all(isinstance(s, PranaSwitch) for s in added)
