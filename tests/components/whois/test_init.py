"""Tests for the Whois integration."""
from unittest.mock import MagicMock

import pytest
from whois.exceptions import (
    FailedParsingWhoisOutput,
    UnknownDateFormat,
    UnknownTld,
    WhoisCommandFailed,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.whois.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_whois: MagicMock,
) -> None:
    """Test the Whois configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_whois.mock_calls) == 2

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [FailedParsingWhoisOutput, UnknownDateFormat, UnknownTld, WhoisCommandFailed],
)
async def test_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_whois: MagicMock,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception,
) -> None:
    """Test the Whois threw an error."""
    mock_config_entry.add_to_hass(hass)
    mock_whois.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_whois.mock_calls) == 1


async def test_import_config(
    hass: HomeAssistant,
    mock_whois: MagicMock,
    mock_whois_config_flow: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the Whois being set up from config via import."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, CONF_DOMAIN: "home-assistant.io"}},
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_whois.mock_calls) == 2
    assert "the Whois platform in YAML is deprecated" in caplog.text
