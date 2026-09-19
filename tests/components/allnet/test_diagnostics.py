"""Tests for the ALLNET diagnostics module."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.allnet.const import (
    CONF_DEVICE_PROFILE,
    CONF_USE_SSL,
    DOMAIN,
)
from homeassistant.components.allnet.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_diagnostics_password_redacted(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    mock_allnet_client: MagicMock,
    mock_device_info: MagicMock,
) -> None:
    """Test that the password is redacted in diagnostics output."""
    entry_with_pw = ConfigEntry(
        data={
            "host": TEST_HOST,
            CONF_USE_SSL: False,
            CONF_PASSWORD: "s3cr3t",
            CONF_DEVICE_PROFILE: "auto",
        },
        discovery_keys={},
        domain=DOMAIN,
        minor_version=1,
        options={},
        source=SOURCE_USER,
        subentries_data=None,
        title="ALLNET Test Device",
        unique_id=TEST_UNIQUE_ID + "pw",
        version=1,
    )

    mock_session = MagicMock()
    with (
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        await hass.config_entries.async_add(entry_with_pw)
        await hass.async_block_till_done()

    assert entry_with_pw.runtime_data is not None

    diag = await async_get_config_entry_diagnostics(hass, entry_with_pw)

    assert diag["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["entry"]["data"]["host"] == TEST_HOST


@pytest.mark.asyncio
async def test_diagnostics_structure(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test the structure of the diagnostics output."""
    entry = setup_integration
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert "entry" in diag
    assert "device" in diag
    assert "coordinator" in diag
    assert "channels" in diag
    assert "channel_count" in diag

    assert "entry_id" in diag["entry"]
    assert "unique_id" in diag["entry"]
    assert "data" in diag["entry"]
    assert "options" in diag["entry"]
    assert diag["entry"]["unique_id"] == TEST_UNIQUE_ID

    assert "last_update_success" in diag["coordinator"]
    assert diag["coordinator"]["last_update_success"] is True

    assert "sensor" in diag["channels"]
    assert "binary_sensor" in diag["channels"]
    assert "switch" in diag["channels"]


@pytest.mark.asyncio
async def test_diagnostics_channel_count(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that channel_count equals total number of channels."""
    entry = setup_integration
    diag = await async_get_config_entry_diagnostics(hass, entry)

    total = sum(len(v) for v in diag["channels"].values())
    assert diag["channel_count"] == total
    assert diag["channel_count"] == 7


@pytest.mark.asyncio
async def test_diagnostics_no_password_no_redaction(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that entries without a password don't get the redacted key."""
    entry = setup_integration
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert CONF_PASSWORD not in diag["entry"]["data"]


@pytest.mark.asyncio
async def test_diagnostics_device_info(
    hass: HomeAssistant, setup_integration: ConfigEntry
) -> None:
    """Test that device info in diagnostics matches what was set up."""
    entry = setup_integration
    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["device"]["manufacturer"] == "ALLNET"
    assert diag["device"]["model"] == "ALL3500"
    assert diag["device"]["sw_version"] == "1.2.3"
