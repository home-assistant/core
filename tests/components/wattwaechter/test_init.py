"""Tests for the WattWächter Plus integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from aio_wattwaechter import (
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterError,
    WattwaechterNoDataError,
)
import pytest

from homeassistant.components.wattwaechter.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_DEVICE_ID, MOCK_HOST

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test successful integration setup and unload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test setup when device is unreachable."""
    mock_client.alive.side_effect = WattwaechterConnectionError("Connection refused")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("side_effect", WattwaechterNoDataError("No data")),
        ("side_effect", WattwaechterConnectionError("Connection refused")),
        ("return_value", None),
    ],
    ids=["no_data", "connection_error", "returns_none"],
)
async def test_setup_entry_retries_on_meter_data_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    attribute: str,
    value: Any,
) -> None:
    """Test setup retries when meter_data fails or returns no data."""
    setattr(mock_client.meter_data, attribute, value)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test an authentication error during setup starts the reauth flow."""
    mock_client.meter_data.side_effect = WattwaechterAuthenticationError(
        "Invalid token"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("system_info_error", "expected_url"),
    [
        (None, "http://wattwaechter-aabbccddeeff.local"),
        (WattwaechterConnectionError("offline"), f"http://{MOCK_HOST}"),
    ],
    ids=["mdns", "ip_fallback"],
)
async def test_device_configuration_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    system_info_error: WattwaechterError | None,
    expected_url: str,
) -> None:
    """Test the configuration URL prefers the mDNS host and falls back to the IP."""
    mock_client.system_info.side_effect = system_info_error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.configuration_url == expected_url
