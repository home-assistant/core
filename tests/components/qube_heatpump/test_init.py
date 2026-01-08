"""Tests for the Qube Heat Pump integration setup and unloading."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import pytest

    from homeassistant.components.qube_heatpump.hub import QubeHub
    from homeassistant.core import HomeAssistant

from unittest.mock import AsyncMock

from homeassistant.components.qube_heatpump import QubeData, async_unload_entry
from homeassistant.components.qube_heatpump.const import CONF_HOST, DOMAIN, PLATFORMS
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


async def test_async_setup_entry_registers_integration(
    hass: HomeAssistant,
) -> None:
    """Test setup entry registers the integration and its hub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    # Use entry.runtime_data which is populated by async_setup_entry
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Integration refactor uses runtime_data
    assert entry.runtime_data is not None
    assert entry.runtime_data.hub.host == "1.2.3.4"


async def test_async_unload_entry_cleans_up(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure unload removes stored data and closes the hub."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "198.51.100.2"})
    entry.add_to_hass(hass)

    unload_platforms = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    class DummyHub:
        async def async_close(self) -> None:  # pragma: no cover - replaced by mock
            return None

    hub = DummyHub()
    hub.async_close = AsyncMock()  # type: ignore[method-assign]

    entry.runtime_data = QubeData(
        hub=cast("QubeHub", hub),
        coordinator=AsyncMock(),
        version="1.0.0",
    )

    result = await async_unload_entry(hass, entry)

    assert result is True
    unload_platforms.assert_called_once_with(entry, PLATFORMS)
    hub.async_close.assert_awaited()
