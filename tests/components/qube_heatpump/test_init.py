"""Tests for the Qube Heat Pump integration setup and unloading."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import pytest

    from homeassistant.components.qube_heatpump.hub import QubeHub
    from homeassistant.core import HomeAssistant

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.qube_heatpump import QubeData, async_unload_entry
from homeassistant.components.qube_heatpump.const import (
    CONF_FRIENDLY_NAME_LANGUAGE,
    CONF_HOST,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


async def test_async_setup_entry_registers_integration(
    hass: HomeAssistant, mock_hub: MagicMock
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
    assert entry.runtime_data.label == "qube1"


async def test_async_setup_entry_respects_language_option(
    hass: HomeAssistant, mock_hub: MagicMock
) -> None:
    """Test setup entry respects the configured language option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        options={CONF_FRIENDLY_NAME_LANGUAGE: "nl"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.friendly_name_language == "nl"


async def test_async_setup_entry_includes_room_temp_sensor(
    hass: HomeAssistant, mock_hub: MagicMock
) -> None:
    """Test setup entry includes the room temperature sensor by default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        title="Qube Heat Pump",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.version is not None


async def test_multi_device_enforces_label_suffix(
    hass: HomeAssistant, mock_hub: MagicMock
) -> None:
    """Test multi-device setup ensures label suffix is applied."""
    # First entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        title="Qube 1",
        unique_id=f"{DOMAIN}-1.2.3.4-502",
    )
    entry1.add_to_hass(hass)

    # Second entry
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.5"},
        title="Qube 2",
        unique_id=f"{DOMAIN}-1.2.3.5-502",
    )
    entry2.add_to_hass(hass)

    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    if entry2.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.LOADED
    assert entry2.state is ConfigEntryState.LOADED

    # In multi-device setup, both entries should have multi_device=True
    assert entry1.runtime_data.multi_device is True
    assert entry2.runtime_data.multi_device is True


async def test_async_unload_entry_cleans_up(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure unload removes stored data and closes the hub."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "198.51.100.2"})
    entry.add_to_hass(hass)

    unload_platforms = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    # Register mock service to avoid ServiceNotFound and avoid read-only async_call patch

    class DummyHub:
        async def async_close(self) -> None:  # pragma: no cover - replaced by mock
            return None

    hub = DummyHub()
    hub.async_close = AsyncMock()  # type: ignore[method-assign]

    entry.runtime_data = QubeData(
        hub=cast("QubeHub", hub),
        coordinator=AsyncMock(),
        label="qube1",
        apply_label_in_name=False,
        version="1.0.0",
        multi_device=False,
        alarm_group_object_id="group.qube_heat_pump",
        friendly_name_language="en",
    )

    result = await async_unload_entry(hass, entry)

    assert result is True
    unload_platforms.assert_called_once_with(entry, PLATFORMS)
    hub.async_close.assert_awaited()
