"""Tests for the Sky Remote component."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sky_remote.const import CONF_LEGACY_CONTROL_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_remote_control() -> Generator[MagicMock]:
    """Mock skyboxremote library."""
    with patch(
        "homeassistant.components.sky_remote.remote.RemoteControl"
    ) as mock_remote_control:
        yield mock_remote_control


async def test_setup_entry(hass: HomeAssistant, mock_remote_control) -> None:
    """Test successful setup of entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "example.com",
            CONF_NAME: "Sky Remote",
            CONF_LEGACY_CONTROL_PORT: False,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    mock_remote_control.assert_called_once_with("example.com", 49160)


async def test_setup_entry_with_legacy_port(
    hass: HomeAssistant, mock_remote_control
) -> None:
    """Test successful setup of entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "example.com",
            CONF_NAME: "Sky Remote",
            CONF_LEGACY_CONTROL_PORT: True,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    mock_remote_control.assert_called_once_with("example.com", 5900)


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "example.com",
            CONF_NAME: "Sky Remote",
            CONF_LEGACY_CONTROL_PORT: True,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
