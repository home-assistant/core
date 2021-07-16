"""Tests for Transmission init."""

from unittest.mock import MagicMock

from transmissionrpc.error import TransmissionError

from homeassistant.components.transmission.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.transmission import MOCK_CONFIG


async def test_setup_with_no_config(hass: HomeAssistant) -> None:
    """Test that we do not discover anything or try to set up a Transmission client."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert DOMAIN not in hass.data


async def test_setup_with_config(hass: HomeAssistant) -> None:
    """Test that we import the config and setup the client."""
    config = {
        DOMAIN: {
            CONF_NAME: "Transmission",
            CONF_HOST: "0.0.0.0",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PORT: 9091,
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that configured transmission is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id]


async def test_auth_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test transmission failed due to an error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("401: Unauthorized")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_conn_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test transmission failed due to an error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    mock_api.side_effect = TransmissionError("111: Connection refused")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing transmission client."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
