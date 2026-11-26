"""Tests for the SMTP integration."""

from unittest.mock import AsyncMock

from aiosmtplib import SMTPAuthenticationError, SMTPException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("smtp", "aiosmtplib")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.services.has_service(NOTIFY_DOMAIN, "home_assistant")

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert not hass.services.has_service(NOTIFY_DOMAIN, "home_assistant")


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (SMTPException(""), ConfigEntryState.SETUP_RETRY),
        (SMTPAuthenticationError(0, ""), ConfigEntryState.SETUP_ERROR),
    ],
)
@pytest.mark.usefixtures("smtp")
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aiosmtplib: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready."""

    aiosmtplib.__aenter__.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state
