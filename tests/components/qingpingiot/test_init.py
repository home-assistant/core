"""Test the qingpingiot init."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_runtime_data_set(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that runtime_data is set after setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator is not None
    assert mock_config_entry.runtime_data.coordinator.mac == "AABBCCDDEEFF"
    assert mock_config_entry.runtime_data.coordinator.model == "cgr1w"


async def test_setup_with_json_model(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
) -> None:
    """Test setup with a JSON protocol model (cgs2)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233445566",
        data={
            CONF_MAC: "112233445566",
            CONF_MODEL: "cgs2",
            CONF_NAME: "Air Monitor",
        },
        title="Air Monitor",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.model == "cgs2"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_mqtt_subscription_started(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that MQTT subscription is started on setup."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mqtt_mock.async_subscribe.assert_called_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
