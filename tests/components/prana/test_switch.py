"""Tests for the Prana switch platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.prana.const import DOMAIN
from homeassistant.components.prana.switch import (
    PranaSwitch,
    PranaSwitchEntityDescription,
    PranaSwitchType,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def coordinator():
    """Mock coordinator for tests. Use SimpleNamespace for .data so getattr works."""
    coord = MagicMock()
    coord.data = SimpleNamespace(
        **{
            PranaSwitchType.BOUND: True,
            PranaSwitchType.HEATER: False,
            PranaSwitchType.WINTER: True,
            PranaSwitchType.AUTO: False,
            PranaSwitchType.AUTO_PLUS: True,
        }
    )
    coord.async_refresh = AsyncMock()
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    # Provide mocked api_client used by entities (do not perform real HTTP in entities)
    coord.api_client = MagicMock()
    coord.api_client.set_switch = AsyncMock(return_value=None)
    return coord


@pytest.fixture
def config_entry(coordinator: MagicMock, hass: HomeAssistant):
    """Mock config entry with runtime_data set to coordinator."""
    entry = MagicMock()
    entry.entry_id = "test_switch_entry"
    entry.data = {"host": "127.0.0.1", "name": "Prana Device"}
    entry.runtime_data = coordinator
    # mirror pattern used by other tests if needed
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    return entry


def test_switch_properties(coordinator: MagicMock, config_entry: MagicMock) -> None:
    """Test switch entity properties (is_on reflects coordinator.data)."""
    bound_desc = PranaSwitchEntityDescription(
        key=PranaSwitchType.BOUND, translation_key="bound"
    )
    bound_switch = PranaSwitch(config_entry, bound_desc)
    assert bound_switch.is_on is True

    heat_desc = PranaSwitchEntityDescription(
        key=PranaSwitchType.HEATER, translation_key="heater"
    )
    heating = PranaSwitch(config_entry, heat_desc)
    assert heating.is_on is False


@pytest.mark.asyncio
async def test_switch_turn_on_off(
    hass: HomeAssistant, coordinator: MagicMock, config_entry: MagicMock
) -> None:
    """Test turning switch on and off triggers API call and refresh."""
    winter_desc = PranaSwitchEntityDescription(
        key=PranaSwitchType.WINTER, translation_key="winter"
    )
    switch = PranaSwitch(config_entry, winter_desc)
    switch.hass = hass

    # initial state True as per fixture
    assert switch.is_on is True

    await switch.async_turn_off()
    coordinator.api_client.set_switch.assert_awaited_with(PranaSwitchType.WINTER, False)
    assert coordinator.async_refresh.await_count >= 1

    # simulate coordinator refresh updating state
    setattr(coordinator.data, PranaSwitchType.WINTER, False)
    assert switch.is_on is False

    await switch.async_turn_on()
    coordinator.api_client.set_switch.assert_awaited_with(PranaSwitchType.WINTER, True)
    assert coordinator.async_refresh.await_count >= 2

    setattr(coordinator.data, PranaSwitchType.WINTER, True)
    assert switch.is_on is True


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, config_entry: MagicMock) -> None:
    """Test setup entry for switch platform adds 5 switches."""
    # Create an async-style coordinator for setup (runtime_data)
    coordinator = AsyncMock()
    coordinator.data = SimpleNamespace(
        **{
            PranaSwitchType.BOUND: True,
            PranaSwitchType.HEATER: False,
            PranaSwitchType.AUTO: True,
            PranaSwitchType.AUTO_PLUS: False,
            PranaSwitchType.WINTER: True,
        }
    )
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.api_client = AsyncMock()
    coordinator.api_client.set_switch = AsyncMock(return_value=None)

    # attach runtime_data to config_entry used by async_setup_entry
    config_entry.runtime_data = coordinator

    added = []

    def async_add_entities(entities):
        added.extend(entities)

    await async_setup_entry(hass, config_entry, async_add_entities)

    # The platform unconditionally adds 5 switches
    assert len(added) == 5
    assert all(isinstance(s, PranaSwitch) for s in added)
