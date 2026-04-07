"""Tests for the HiVi Speaker integration init and setup."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hivi_speaker import (
    async_remove_config_entry_device,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.hivi_speaker.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a config entry for tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HiVi Speaker",
        data={},
    )


async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry: device manager is created and platforms are loaded."""
    config_entry.add_to_hass(hass)

    mock_device_manager = AsyncMock()
    mock_device_manager.async_setup = AsyncMock(return_value=None)

    with (
        patch(
            "homeassistant.components.hivi_speaker.HIVIDeviceManager",
            return_value=mock_device_manager,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_forward_setups,
    ):
        result = await async_setup_entry(hass, config_entry)

    assert result is True
    mock_device_manager.async_setup.assert_awaited_once()
    mock_forward_setups.assert_awaited_once_with(config_entry, ["switch"])

    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN][config_entry.entry_id]["device_manager"] is mock_device_manager


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry: device manager is cleaned up and entry data removed."""
    config_entry.add_to_hass(hass)

    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, config_entry)

    assert result is True
    mock_device_manager.async_cleanup.assert_awaited_once()
    mock_unload_platforms.assert_awaited_once_with(config_entry, ["switch"])
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_unload_entry_no_device_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry when device_manager is missing (e.g. partial cleanup)."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {}

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is True
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_async_remove_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_remove_entry clears device registry loop and removes storage."""
    config_entry.add_to_hass(hass)
    mock_reg = MagicMock()
    mock_reg.devices = {}

    with (
        patch(
            "homeassistant.components.hivi_speaker.dr.async_get",
            return_value=mock_reg,
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            new_callable=AsyncMock,
        ) as mock_store_remove,
    ):
        await async_remove_entry(hass, config_entry)

    mock_store_remove.assert_awaited_once()


async def test_unload_entry_platform_unload_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry when async_unload_platforms returns False."""
    config_entry.add_to_hass(hass)
    mock_device_manager = AsyncMock()
    mock_device_manager.async_cleanup = AsyncMock(return_value=None)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_device_manager,
    }

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        result = await async_unload_entry(hass, config_entry)

    assert result is False
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_remove_config_entry_device_not_our_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal hook returns False when identifiers are not DOMAIN."""
    config_entry.add_to_hass(hass)
    device = SimpleNamespace(identifiers={("mqtt", "other")})

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is False


async def test_remove_config_entry_device_no_device_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal allows HA delete when device_manager is missing."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {}
    device = SimpleNamespace(
        id="ha-device-1",
        identifiers={(DOMAIN, "udn-1")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is True


async def test_remove_config_entry_device_with_manager(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device removal cleans entities, registry data, and control switches."""
    config_entry.add_to_hass(hass)
    mock_dm = MagicMock()
    mock_dm.async_remove_entities_for_device = AsyncMock()
    mock_dm.device_data_registry = MagicMock()
    mock_dm.device_data_registry.get_device_dict_by_ha_device_id = MagicMock(
        return_value={
            "speaker_device_id": "spk-udn",
            "friendly_name": "Spk",
            "ha_device_id": "ha-device-1",
        }
    )
    mock_dm.device_data_registry.async_remove_device_data = AsyncMock()
    mock_dm.remove_control_entities_by_speaker_device_id = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device_manager": mock_dm,
    }
    device = SimpleNamespace(
        id="ha-device-1",
        identifiers={(DOMAIN, "udn-1")},
    )

    result = await async_remove_config_entry_device(hass, config_entry, device)

    assert result is True
    mock_dm.async_remove_entities_for_device.assert_awaited_once_with("ha-device-1")
    mock_dm.device_data_registry.async_remove_device_data.assert_awaited_once_with(
        "ha-device-1"
    )
    mock_dm.remove_control_entities_by_speaker_device_id.assert_awaited_once_with(
        "spk-udn"
    )
