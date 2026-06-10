"""BleBox devices setup tests."""

import logging

import blebox_uniapi
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    async_setup_config_entry,
    patch_product_identify,
    setup_product_mock,
)

from tests.common import MockConfigEntry


async def test_setup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ClientError)

    caplog.set_level(logging.ERROR)
    await async_setup_config_entry(hass, config_entry)

    assert "Identify failed at 172.100.123.4:80 ()" in caplog.text
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failure_on_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ConnectionError)

    caplog.set_level(logging.ERROR)
    await async_setup_config_entry(hass, config_entry)

    assert "Identify failed at 172.100.123.4:80 ()" in caplog.text
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that unloading works properly."""
    setup_product_mock("switches", [])

    await async_setup_config_entry(hass, config_entry)
    assert hasattr(config_entry, "runtime_data")

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hasattr(config_entry, "runtime_data")

    assert config_entry.state is ConfigEntryState.NOT_LOADED
