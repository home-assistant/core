"""Tests for the AdGuard Home."""

from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, mock_adguard)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup failed."""
    mock_adguard.version.side_effect = AdGuardHomeConnectionError("Connection error")

    await setup_integration(hass, mock_config_entry, mock_adguard)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_legacy_entry_without_path(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
) -> None:
    """Test setup still works for legacy entries without stored base path."""
    config_entry = MockConfigEntry(
        domain="adguard",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 3000,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        title="AdGuard Home",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.adguard.PLATFORMS", []),
        patch(
            "homeassistant.components.adguard.AdGuardHome", return_value=mock_adguard
        ) as adguard,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    adguard.assert_called_once_with(
        "127.0.0.1",
        base_path="/control",
        port=3000,
        username="user",
        password="pass",
        tls=False,
        verify_ssl=True,
        session=adguard.call_args.kwargs["session"],
    )
    assert config_entry.state is ConfigEntryState.LOADED
